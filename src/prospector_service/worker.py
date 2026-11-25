import json
import os
import queue
import sys
import threading
import time

from .process_tree import enable_subreaper, reap_orphans


def main(execute=None):
    # Reserve stdout for the protocol before importing libraries that may write to it.
    channel = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=65536)
    with open(os.devnull, "wb") as sink:
        os.dup2(sink.fileno(), sys.stdout.fileno())

    incoming = os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0)
    max_bytes = int(sys.argv[1])
    enable_subreaper()
    from prospector_engine import CancellationToken

    from .adapters.engine import execute_batch
    from .schemas import BatchRequest, utc_now

    def write(message):
        data = json.dumps(message, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        if len(data) > max_bytes:
            data = b'{"type":"error","code":"IPC_LIMIT"}\n'
        channel.write(data)
        channel.flush()

    write({"type": "ready"})

    def read_exact(count):
        data = bytearray()
        while len(data) < count:
            chunk = incoming.read(count - len(data))
            if not chunk:
                raise EOFError("incomplete IPC frame")
            data.extend(chunk)
        return data

    size = int.from_bytes(read_exact(4), "big")
    if size > max_bytes:
        raise ValueError("request exceeds IPC")
    config = json.loads(read_exact(size))
    token = CancellationToken()

    def watch_cancellation():
        if incoming.readline(16) in {b"cancel\n", b""}:
            token.request_cancel()

    threading.Thread(target=watch_cancellation, daemon=True).start()
    outgoing = queue.Queue(maxsize=96)
    last_progress = float("-inf")

    def send(message):
        nonlocal last_progress
        if message["type"] == "running":
            last_progress = float("-inf")
        if message["type"] == "progress":
            now = time.monotonic()
            if now - last_progress < 0.1 or outgoing.qsize() >= 72:
                return
            last_progress = now
        if message["type"] in {"progress", "running", "awaiting"}:
            message["timestamp"] = utc_now().isoformat()
        outgoing.put_nowait(message)

    def relay():
        while (message := outgoing.get()) is not None:
            write(message)

    thread = threading.Thread(target=relay, daemon=True)
    thread.start()
    try:
        batch = BatchRequest.model_validate(config["batch"])
        send({"type": "started"})
        (execute or execute_batch)(batch, config["browser"], config["headless"], token, send)
    except Exception:
        send({"type": "error", "code": "ENGINE_EXECUTION_FAILED"})
    finally:
        deadline = time.monotonic() + 20
        while not (clean := reap_orphans()) and time.monotonic() < deadline:
            time.sleep(0.05)
        send({"type": "cleanup", "verified": clean})
        outgoing.put(None)
        thread.join()
        if not clean:
            # Keep the subreaper alive so the coordinator can verify forced cleanup.
            threading.Event().wait()


if __name__ == "__main__":
    main()
