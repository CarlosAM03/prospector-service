"""Bounded real ASGI/browser readiness smoke; no accepted Jobs or Google Maps calls."""

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
        "INTERNAL_API_KEY=container-inbound-test",
        "-e",
        "CALLBACK_API_KEY=container-outbound-test",
        "-e",
        "PLATFORM_CALLBACK_ORIGIN=http://127.0.0.1:9000",
        "-e",
        "ALLOW_LOCAL_CALLBACKS=true",
        options.image,
    )
    try:
        port = docker("port", container, "8000/tcp").splitlines()[0].rsplit(":", 1)[1]
        origin = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 45
        while True:
            try:
                with urllib.request.urlopen(origin + "/health/ready", timeout=2) as response:
                    ready = json.load(response)
                assert ready["status"] == "ready"
                break
            except (OSError, AssertionError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("container readiness did not become healthy") from None
                time.sleep(0.5)
        with urllib.request.urlopen(origin + "/health/live", timeout=2) as response:
            assert json.load(response)["status"] == "alive"
        job = "c" + "1" * 24
        body = {
            "jobId": job,
            "tenantId": "c" + "2" * 24,
            "query": {"keyword": "cafe", "location": "TJ", "source": "google_maps", "limit": 1},
            "callbackUrl": f"http://127.0.0.1:9000/api/v1/internal/prospecting-jobs/{job}/events",
        }
        request = urllib.request.Request(
            origin + "/api/v1/prospecting/jobs",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as error:
            assert error.code == 401
        else:
            raise AssertionError("container accepted an unauthenticated Job")
        print("CONTAINER_ASGI_BROWSER_HEALTH_SMOKE_PASS (no Maps)")
    finally:
        docker("stop", "--time", "20", container)


if __name__ == "__main__":
    main()
