"""Exercise the real container ASGI admission boundary without external extraction."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request


def docker(*args):
    result = subprocess.run(["docker", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="prospector-service:ci")
    options = parser.parse_args()
    container = docker(
        "run",
        "-d",
        "--rm",
        "--init",
        "--shm-size=1g",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "-p",
        "127.0.0.1::8000",
        "-e",
        "APP_ENV=test",
        "-e",
        f"INTERNAL_API_KEY={'a' * 32}",
        "-e",
        f"ASSERTION_KEY={'b' * 32}",
        "-e",
        f"METADATA_KEY={'c' * 32}",
        "-e",
        f"CALLBACK_API_KEY={'d' * 32}",
        "-e",
        "ALLOW_LOCAL_CALLBACKS=true",
        "-e",
        "PLATFORM_CALLBACK_ORIGIN=http://127.0.0.1:9000",
        options.image,
    )
    try:
        port = docker("port", container, "8000/tcp").splitlines()[0].rsplit(":", 1)[1]
        origin = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 45
        while True:
            try:
                with urllib.request.urlopen(origin + "/health/ready", timeout=2) as response:
                    assert json.load(response)["status"] == "ready"
                break
            except (OSError, AssertionError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("container readiness did not become healthy") from None
                time.sleep(0.5)
        with urllib.request.urlopen(origin + "/health/live", timeout=2) as response:
            assert json.load(response)["status"] == "alive"
        for path, code in (("/api/v1/prospecting/batches", 401), ("/api/v1/prospecting/jobs", 404)):
            request = urllib.request.Request(
                origin + path,
                data=b"{}",
                headers={"Idempotency-Key": "test", "Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(request, timeout=2)
            except urllib.error.HTTPError as error:
                assert error.code == code
            else:
                raise AssertionError("container accepted an unauthenticated request")
        print("CONTAINER_ASGI_BATCH_BOUNDARY_PASS")
    finally:
        docker("stop", "--time", "20", container)


if __name__ == "__main__":
    main()
