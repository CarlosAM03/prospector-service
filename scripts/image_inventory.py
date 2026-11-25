"""Record versions from the installed, final image without launching a browser."""

import json
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, distributions, metadata, version
from pathlib import Path

import playwright

PIN = "68aca39b42a21ae8c0b54b6e6ca93840fdad27e5"


def output(*command):
    return subprocess.check_output(command, text=True).strip()


def main():
    (shell,) = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]).glob(
        "chromium_headless_shell-*/*/chrome-headless-shell"
    )
    node = Path(playwright.__file__).parent / "driver" / "node"
    info = {
        "python": platform.python_version(),
        "pip": version("pip"),
        "playwright": version("playwright"),
        "soupsieve": version("soupsieve"),
        "engine_version": version("prospector-engine"),
        "engine_required_commit": PIN,
        "chromium": output(str(shell), "--version"),
        "driver_node": output(str(node), "--version"),
        "libatomic1": output("dpkg-query", "-W", "-f=${Version}", "libatomic1"),
        "debian": output("dpkg-query", "-W", "-f=${Package}= ${Version}\\n").splitlines(),
        "python_distributions": sorted(
            f"{item.metadata['Name']}=={item.version}" for item in distributions()
        ),
    }
    assert info["python"] == "3.11.18"
    assert info["pip"] == "26.3"
    assert info["playwright"] == "1.65.2"
    assert info["soupsieve"] == "4.1.3"
    assert "159.0.8154.6" in info["chromium"]
    assert info["driver_node"] == "v26.13.1"
    assert any(PIN in item for item in metadata("prospector-service").get_all("Requires-Dist"))
    for name in ("setuptools", "wheel", "pyee"):
        try:
            version(name)
        except PackageNotFoundError:
            continue
        raise AssertionError(f"unexpected installed distribution: {name}")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
