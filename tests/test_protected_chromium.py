import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import protected_chromium

UPSTREAM_SHA = "cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849"
CHROOT_SHA = "ed2a8324b75c5239135511d592b612ef0caf51a7ccee2347af6228110dc38173"
SERVICE_SHA = "f186342fd7e65bf0344df4b7bbe6b6735a92727a89c8e48cc7fa43630e1067f1"


class TestProtectedProfiles(TestCase):
    def test_loads_exact_upstream_blob_without_network(self):
        with (
            TemporaryDirectory() as scratch,
            patch("socket.socket", side_effect=AssertionError("network socket")),
            patch("urllib.request.urlopen", side_effect=AssertionError("HTTP download")),
            patch("subprocess.Popen", side_effect=AssertionError("external downloader")),
        ):
            upstream = protected_chromium.profiles(Path(scratch))[1][1]
            content = upstream.read_bytes()
        self.assertEqual(content, protected_chromium.PROFILE_PATH.read_bytes())
        self.assertEqual(hashlib.sha256(content).hexdigest(), UPSTREAM_SHA)

    def test_preserves_four_profiles_and_historical_variant_bytes(self):
        with TemporaryDirectory() as scratch:
            default, upstream, chroot, service = protected_chromium.profiles(Path(scratch))
            self.assertEqual(default, ("docker-default", None, True))
            self.assertEqual((upstream[0], upstream[2]), ("playwright-upstream", False))
            self.assertEqual((chroot[0], chroot[2]), ("playwright-chroot-lab", False))
            self.assertEqual((service[0], service[2]), ("service-pidfd-lab", True))

            original = json.loads(upstream[1].read_bytes())
            chroot_rule = {
                "names": ["chroot"],
                "action": "SCMP_ACT_ALLOW",
                "args": [],
                "includes": {},
                "excludes": {},
            }
            chroot_expected = {**original, "syscalls": [*original["syscalls"], chroot_rule]}
            pidfd_rule = {**chroot_rule, "names": ["pidfd_open", "pidfd_send_signal"]}
            service_expected = {**original, "syscalls": [*chroot_expected["syscalls"], pidfd_rule]}
            for output, expected, digest in (
                (chroot[1], chroot_expected, CHROOT_SHA),
                (service[1], service_expected, SERVICE_SHA),
            ):
                content = output.read_bytes()
                self.assertEqual(json.loads(content), expected)
                self.assertEqual(hashlib.sha256(content).hexdigest(), digest)

    def test_rejects_missing_profile_without_generating_outputs(self):
        with TemporaryDirectory() as scratch:
            directory = Path(scratch)
            with (
                patch.object(protected_chromium, "PROFILE_PATH", directory / "missing.json"),
                self.assertRaisesRegex(FileNotFoundError, "missing.json"),
            ):
                protected_chromium.profiles(directory)
            self.assertEqual(list(directory.iterdir()), [])

    def test_rejects_tampered_profile_without_generating_outputs(self):
        with TemporaryDirectory() as scratch:
            directory = Path(scratch)
            tampered = directory / "tampered.json"
            tampered.write_bytes(protected_chromium.PROFILE_PATH.read_bytes() + b" ")
            with (
                patch.object(protected_chromium, "PROFILE_PATH", tampered),
                self.assertRaisesRegex(ValueError, "profile hash mismatch"),
            ):
                protected_chromium.profiles(directory)
            self.assertEqual(list(directory.iterdir()), [tampered])
