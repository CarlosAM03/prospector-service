"""Run an isolated Docker + TLS + Nginx smoke against the batch API and Platform fixture."""

import argparse
import base64
import functools
import hashlib
import hmac
import json
import os
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

BASE = "/api/v1/prospecting/batches"
ROOT = Path(__file__).resolve().parents[1]


def docker(*arguments, check=True):
    command = subprocess.run(["docker", *arguments], capture_output=True, text=True)
    if check and command.returncode:
        raise RuntimeError(command.stderr.strip())
    return command.stdout.strip()


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def request_headers(verb, path, body=b"", key="", tenant=1, owner=1):
    now = int(time.time())
    path, _, query = path.partition("?")
    scope = "prospecting:batches:create"
    if verb == "GET":
        scope = (
            "prospecting:results:export" if path.endswith("/export") else "prospecting:results:read"
        )
    claims = {
        "iss": "platform",
        "aud": "prospector-service/v1",
        "iat": now,
        "exp": now + 100,
        "solutionId": "prospector-solution",
        "sub": f"c{owner:024d}",
        "tenantId": f"c{tenant:024d}",
        "actorType": "owner",
        "method": verb,
        "path": path,
        "query": query,
        "idempotencyKey": key,
        "bodySha256": hashlib.sha256(body).hexdigest(),
        "scope": scope,
    }
    unsigned = encode(b'{"alg":"HS256","typ":"JWT"}') + b"." + encode(json.dumps(claims).encode())
    sig = encode(hmac.digest(b"b" * 32, unsigned, "sha256"))
    return {
        "X-API-Key": "a" * 32,
        "X-Platform-Assertion": (unsigned + b"." + sig).decode(),
        "Idempotency-Key": key,
        "Content-Type": "application/json",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="prospector-service:ci")
    parser.add_argument("--nginx-image", default="nginxinc/nginx-unprivileged:1.28-alpine")
    args = parser.parse_args()
    name = "prospector-gate-" + uuid4().hex[:10]
    engine, nginx, volume = name + "-service", name + "-nginx", name + "-metadata"
    with tempfile.TemporaryDirectory(prefix="prospector-nginx-") as scratch:
        temp = Path(scratch)
        cert, key, acl = temp / "tls.crt", temp / "tls.key", temp / "allow.conf"
        acl.write_text("allow all;\n")
        openssl_config = temp / "openssl.cnf"
        openssl_config.write_text("[req]\nprompt=no\ndistinguished_name=dn\n[dn]\nCN=localhost\n")
        generated = subprocess.run(
            [
                os.getenv("OPENSSL_BIN", "openssl"),
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-config",
                str(openssl_config),
                "-addext",
                "subjectAltName=DNS:localhost,DNS:nginx",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            capture_output=True,
            text=True,
        )
        if generated.returncode:
            raise RuntimeError(generated.stderr.strip())
        for path in (cert, key, acl):
            path.chmod(0o644)
        context = ssl.create_default_context(cafile=str(cert))
        docker("network", "create", name)
        try:
            docker("volume", "create", volume)
            docker(
                "run",
                "-d",
                "--name",
                engine,
                "--network",
                name,
                "--network-alias",
                "service",
                "--init",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--read-only",
                "--shm-size=1g",
                "--memory=512m",
                "--memory-swap=512m",
                "--ulimit",
                "core=0",
                "--tmpfs",
                "/run/prospector-tmp:size=64m,uid=10001,gid=10001,mode=0700",
                "-e",
                "WORKER_TEMP_DIR=/run/prospector-tmp",
                "-v",
                f"{volume}:/var/lib/prospector",
                "-v",
                f"{ROOT}:/gate:ro",
                "-v",
                f"{cert}:/test-ca.crt:ro",
                "--workdir",
                "/gate",
                "-e",
                "PYTHONPATH=/gate/src:/gate",
                "-e",
                "APP_ENV=test",
                "-e",
                "MAX_ACTIVE_BATCHES=25",
                "-e",
                f"INTERNAL_API_KEY={'a' * 32}",
                "-e",
                f"ASSERTION_KEY={'b' * 32}",
                "-e",
                f"METADATA_KEY={'c' * 32}",
                "-e",
                f"CALLBACK_API_KEY={'d' * 32}",
                "-e",
                "PLATFORM_CALLBACK_CA_FILE=/test-ca.crt",
                "-e",
                "PLATFORM_CALLBACK_ORIGIN=https://nginx:8443",
                args.image,
                "python",
                "-m",
                "scripts.proxy_fixture",
            )
            docker(
                "run",
                "-d",
                "--name",
                nginx,
                "--network",
                name,
                "--network-alias",
                "nginx",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--tmpfs",
                "/tmp:uid=101,gid=101,mode=0700",
                "-p",
                "127.0.0.1::8443",
                "-v",
                f"{ROOT / 'deploy/nginx/nginx.conf'}:/etc/nginx/nginx.conf:ro",
                "-v",
                f"{acl}:/etc/nginx/platform-allow.conf:ro",
                "-v",
                f"{cert}:/run/secrets/tls_crt:ro",
                "-v",
                f"{key}:/run/secrets/tls_key:ro",
                "--entrypoint",
                "nginx",
                args.nginx_image,
                "-g",
                "daemon off;",
            )
            port = docker("port", nginx, "8443/tcp").rsplit(":", 1)[1]
            origin = f"https://localhost:{port}"

            def request(path, *, body=None, headers=None):
                message = urllib.request.Request(origin + path, data=body, headers=headers or {})
                try:
                    with urllib.request.urlopen(message, context=context, timeout=5) as result:
                        return result.status, result.read()
                except urllib.error.HTTPError as exc:
                    return exc.code, exc.read()

            def await_state(predicate):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    try:
                        if predicate():
                            return
                    except OSError:
                        pass
                    time.sleep(0.15)
                raise RuntimeError("proxy gate timed out")

            await_state(lambda: request("/health/ready")[0] == 200)
            assert request(BASE, body=b"X" * 65537)[0] == 413
            assert request("/api/v1/prospecting/jobs", body=b"{}")[0] == 404
            assert request(BASE, body=b"{}", headers={"Idempotency-Key": "test"})[0] == 401
            config = docker("exec", nginx, "nginx", "-T")
            assert "proxy_next_upstream off;" in config and "proxy_max_temp_file_size 0;" in config
            fixtures = []
            for index in range(1, 26):
                bid, jid = f"c{index:024d}", f"c{index + 100:024d}"
                payload = json.dumps(
                    {
                        "batchId": bid,
                        "jobs": [
                            {
                                "jobId": jid,
                                "query": {
                                    "keyword": "SYNTHETIC_QUERY_SENTINEL",
                                    "location": "controlled",
                                    "source": "google_maps",
                                    "limit": 1,
                                },
                            }
                        ],
                    }
                ).encode()
                headers = request_headers(
                    "POST", BASE, payload, bid, (index - 1) // 5 + 1, (index - 1) % 5 + 1
                )
                fixtures.append((bid, jid, payload, headers))
            with ThreadPoolExecutor(max_workers=25) as pool:
                handles = [
                    pool.submit(functools.partial(request, BASE, body=body, headers=headers))
                    for _, _, body, headers in fixtures
                ]
                replies = [handle.result() for handle in handles]
            assert [status for status, _ in replies] == [202] * 25

            def events():
                return json.loads(request("/__fixture/events")[1])

            await_state(
                lambda: len([event for event in events() if event["kind"] == "TERMINAL"]) == 25
            )
            assert any(event["kind"] == "PROGRESS" for event in events())
            bid, jid, payload, headers = fixtures[0]
            assert request(BASE, body=payload, headers=headers) == replies[0]
            result = f"{BASE}/{bid}/jobs/{jid}/results"
            assert request(result, headers=request_headers("GET", result))[0] == 200
            xlsx = f"{BASE}/{bid}/jobs/{jid}/export?format=xlsx"
            export_status, content = request(xlsx, headers=request_headers("GET", xlsx))
            assert export_status == 200 and content.startswith(b"PK")
            # A truncated upload must neither become an admission nor be retried by Nginx.
            incomplete_id = "c" + "9" * 24
            incomplete = payload.replace(bid.encode(), incomplete_id.encode()).replace(
                jid.encode(), ("c" + "8" * 24).encode()
            )
            incomplete_headers = request_headers("POST", BASE, incomplete, incomplete_id)
            wire = (
                f"POST {BASE} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(incomplete)}\r\n"
            )
            wire += "".join(f"{name}: {value}\r\n" for name, value in incomplete_headers.items())
            with socket.create_connection(("127.0.0.1", int(port)), timeout=5) as connection:
                with context.wrap_socket(connection, server_hostname="localhost") as secure:
                    secure.sendall(wire.encode() + b"\r\n" + incomplete[: len(incomplete) // 2])
            assert request(BASE, body=incomplete, headers=incomplete_headers)[0] == 202
            await_state(
                lambda: len([event for event in events() if event["kind"] == "TERMINAL"]) == 26
            )
            scanner = (
                "import resource; from pathlib import Path; "
                "paths=list(Path('/var/lib/prospector').glob('*.sqlite3*')); "
                "assert any(p.name.endswith('-wal') for p in paths); "
                "assert all(b'SYNTHETIC_' not in p.read_bytes() for p in paths); "
                "assert not list(Path('/run/prospector-tmp').iterdir()); "
                "assert resource.getrlimit(resource.RLIMIT_CORE)==(0,0); "
                "assert Path('/sys/fs/cgroup/memory.swap.max').read_text().strip()=='0'"
            )
            docker("exec", engine, "python", "-c", scanner)
            for container in (engine, nginx):
                logs = subprocess.check_output(
                    ["docker", "logs", container], stderr=subprocess.STDOUT
                )
                assert b"SYNTHETIC_" not in logs
            docker("restart", "--time", "75", engine)
            await_state(lambda: request("/health/ready")[0] == 200)
            assert request(BASE, body=payload, headers=headers) == replies[0]
            assert request(result, headers=request_headers("GET", result))[0] == 410
            print("NGINX_TLS_BATCH_CALLBACK_RESTART_VOLATILITY_PASS")
        except Exception:
            print(docker("logs", "--tail", "20", engine, check=False))
            print(docker("logs", "--tail", "20", nginx, check=False))
            raise
        finally:
            docker("rm", "-f", nginx, engine, check=False)
            docker("volume", "rm", volume, check=False)
            docker("network", "rm", name, check=False)


if __name__ == "__main__":
    main()
