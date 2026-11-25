import asyncio
import json
import os
import shutil
import signal
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .process_tree import terminate_tree

RUN_TIMEOUT = 120 * 60
CANCEL_GRACE = 30
TERMINATE_GRACE = 30


def memory_filesystem(path: Path) -> bool:
    if sys.platform != "linux":
        return False
    try:
        directory = path.resolve(strict=True)
        mounts = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            mount = Path(left.split()[4].replace(r"\040", " "))
            if directory.is_relative_to(mount):
                mounts.append((len(mount.parts), right.split()[0]))
        return bool(mounts) and max(mounts)[1] in {"tmpfs", "ramfs"}
    except (OSError, ValueError):
        return False


@dataclass(frozen=True)
class Execution:
    result: dict | None = None
    error: str = "ENGINE_EXIT"
    clean: bool = True


class ProcessRunner:
    supported = sys.platform == "linux" and hasattr(os, "pidfd_open")

    def __init__(self, settings: Settings):
        self.settings = settings
        self.supported = self.supported and memory_filesystem(settings.worker_temp_dir)
        if self.supported:
            try:
                descriptor = os.pidfd_open(os.getpid())
                try:
                    signal.pidfd_send_signal(descriptor, 0)
                finally:
                    os.close(descriptor)
            except OSError:
                self.supported = False

    def command(self):
        return sys.executable, "-m", "prospector_service.worker", str(self.settings.ipc_max_bytes)

    async def run(self, batch, notify, stop: asyncio.Event) -> Execution:
        if not self.supported:
            return Execution(error="RUNTIME_UNAVAILABLE")
        settings = self.settings
        directory = Path(tempfile.mkdtemp(prefix="prospector-", dir=settings.worker_temp_dir))
        env = {
            key: os.environ[key]
            for key in ("PATH", "LANG", "LC_ALL", "PLAYWRIGHT_BROWSERS_PATH", "PYTHONPATH")
            if key in os.environ
        }
        env.update(
            HOME=str(directory),
            TMPDIR=str(directory),
            PYTHONDONTWRITEBYTECODE="1",
            PROSPECTOR_CHROMIUM_SANDBOX=settings.prospector_chromium_sandbox,
        )
        process = None
        clean = False
        try:
            process = await asyncio.create_subprocess_exec(
                *self.command(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                limit=settings.ipc_max_bytes,
                start_new_session=True,
            )
            execution = await self._coordinate(process, batch, notify, stop)
            clean = execution.clean
            return execution
        except OSError:
            return Execution(error="WORKER_START_FAILED", clean=process is None)
        finally:
            if process is None or clean:
                try:
                    shutil.rmtree(directory)
                except OSError:
                    # The process tree is gone. Temp storage still belongs to the volatile mount.
                    pass

    async def _coordinate(self, process, batch, notify, stop):
        result = None
        error = "ENGINE_EXIT"
        reason = None
        cleanup = False
        started = asyncio.Event()

        async def read():
            line = await process.stdout.readline()
            if not line:
                return None
            if len(line) > self.settings.ipc_max_bytes:
                raise ValueError("IPC limit")
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("invalid IPC message")
            return message

        async def receive():
            nonlocal result, error, cleanup
            async with asyncio.timeout(15):
                if await read() != {"type": "ready"}:
                    raise ValueError("worker handshake failed")
                request = {
                    "batch": batch.model_dump(mode="json"),
                    "browser": self.settings.engine_browser,
                    "headless": self.settings.engine_headless,
                }
                payload = json.dumps(request, ensure_ascii=False).encode()
                if len(payload) > self.settings.ipc_max_bytes:
                    raise ValueError("request exceeds IPC")
                process.stdin.write(len(payload).to_bytes(4, "big") + payload)
                await process.stdin.drain()
                if await read() != {"type": "started"}:
                    raise ValueError("worker did not start")
            started.set()
            while (message := await read()) is not None:
                kind = message["type"]
                if kind == "result":
                    result = message
                elif kind == "cleanup":
                    cleanup = message.get("verified") is True
                    if not cleanup:
                        raise ValueError("worker reported incomplete cleanup")
                elif kind == "error":
                    error = "IPC_LIMIT" if message.get("code") == "IPC_LIMIT" else "ENGINE_FAILED"
                elif kind in {"running", "awaiting", "progress"} and result is None:
                    notify(message)
                else:
                    raise ValueError("invalid IPC phase")
            return await process.wait() == 0 and cleanup

        receiver = asyncio.create_task(receive())
        start = asyncio.create_task(started.wait())
        stopping = asyncio.create_task(stop.wait())
        loop = asyncio.get_running_loop()
        try:
            done, _ = await asyncio.wait(
                {receiver, start, stopping}, timeout=16, return_when=asyncio.FIRST_COMPLETED
            )
            if receiver in done:
                clean = receiver.result()
                return Execution(result, error, clean)
            if start in done and not stop.is_set():
                done, _ = await asyncio.wait(
                    {receiver, stopping}, timeout=RUN_TIMEOUT, return_when=asyncio.FIRST_COMPLETED
                )
                if receiver in done:
                    return Execution(result, error, receiver.result())
            reason = (
                "SERVICE_DRAINING"
                if stop.is_set()
                else ("BATCH_TIMEOUT" if started.is_set() else "WORKER_START_FAILED")
            )
            deadline = loop.time() + CANCEL_GRACE
            try:
                async with asyncio.timeout(min(1, CANCEL_GRACE)):
                    process.stdin.write(b"cancel\n")
                    await process.stdin.drain()
            except (OSError, RuntimeError, TimeoutError):
                pass
            done, _ = await asyncio.wait({receiver}, timeout=max(0, deadline - loop.time()))
            if done and receiver.result():
                return Execution(result, reason, True)
        except (ValueError, TimeoutError, OSError, KeyError):
            reason = reason or "WORKER_PROTOCOL"
        finally:
            for task in (start, stopping):
                task.cancel()
            await asyncio.gather(start, stopping, return_exceptions=True)
            if not receiver.done():
                receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
            process.stdin.close()
            if process.returncode is None:
                verified = await terminate_tree(process, loop.time() + TERMINATE_GRACE)
                if not verified and process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
            else:
                verified = False
        return Execution(result, reason or error, verified)
