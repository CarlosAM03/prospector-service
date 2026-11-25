"""Subprocess fixture for the Linux IPC integration gates."""

import os
import sys
import time
from pathlib import Path

from prospector_service.worker import main


def run(batch, browser, headless, token, send):
    assert all(
        name not in os.environ
        for key in ("INTERNAL_API_KEY", "CALLBACK_API_KEY", "ASSERTION_KEY", "METADATA_KEY")
        for name in (key, f"{key}_FILE")
    )
    assert os.environ.get("PROSPECTOR_CHROMIUM_SANDBOX") == sys.argv[4]
    gate = Path(sys.argv[2])
    if sys.argv[3] == "acl_probe":
        assert (gate.parent / "credential-fixture").read_text() == "synthetic-read-probe"
        assert os.access(gate.parent / "metadata.sqlite3", os.R_OK | os.W_OK)
    if len(sys.argv) > 3 and sys.argv[3] == "wedged":
        import subprocess

        subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True
        )
        send({"type": "running", "index": 0})
        time.sleep(120)
        return
    entries = []
    for index, job in enumerate(batch.jobs):
        send({"type": "running", "index": index})
        send(
            {
                "type": "progress",
                "index": index,
                "progress": {
                    "kind": "metric_updated",
                    "name": "requested_limit",
                    "value": job.query.limit,
                },
            }
        )
        if index == 0:
            while not gate.exists():
                if token.is_cancelled:
                    return
                time.sleep(0.01)
        send({"type": "awaiting", "index": index})
        entries.append({"status": "COMPLETED", "quality": "SUCCESS", "rows": []})
    send({"type": "result", "entries": entries, "interrupted": None})


if __name__ == "__main__":
    main(run)
