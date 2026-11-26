"""Generate the ratified Service seccomp profile from the pinned upstream input."""

import argparse
import hashlib
import tempfile
from pathlib import Path

from scripts.protected_chromium import SERVICE_PROFILE_HASH, profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        with tempfile.TemporaryDirectory() as scratch:
            profiles(Path(scratch))
            with args.file.open("xb") as output:
                output.write((Path(scratch) / "service-seccomp-lab.json").read_bytes())
    actual = hashlib.sha256(args.file.read_bytes()).hexdigest()
    if actual != SERVICE_PROFILE_HASH:
        raise SystemExit("Service seccomp profile fingerprint differs from SEC-003")
    print(actual)


if __name__ == "__main__":
    main()
