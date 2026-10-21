import io
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import ExportFileExistsError, ExportWriteError, InvalidExportInput
from .formats import ExportFormat

_SAFE_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\.(csv|xlsx)\Z")


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    filename: str
    content_type: str
    content: bytes
    format: ExportFormat

    def __post_init__(self) -> None:
        if not isinstance(self.filename, str) or not _SAFE_FILENAME.fullmatch(self.filename):
            raise InvalidExportInput("filename must be a safe ASCII basename")
        if not isinstance(self.format, ExportFormat):
            raise InvalidExportInput("artifact format must be ExportFormat")
        if not self.filename.endswith("." + self.format.value):
            raise InvalidExportInput("filename extension must match format")
        if self.content_type != self.format.content_type or not isinstance(self.content, bytes):
            raise InvalidExportInput("artifact must contain bytes and the format MIME type")
        if self.filename.split(".")[0].upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "CONIN$",
            "CONOUT$",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            raise InvalidExportInput("reserved filename")

    def open_binary(self) -> io.BytesIO:
        """Return a fresh, caller-owned binary stream over the completed bytes."""
        return io.BytesIO(self.content)

    def save(self, directory: str | Path) -> Path:
        """Publish atomically without overwrite, in an existing trusted directory.

        Requires local filesystem hard-link support; never falls back to overwriting.
        """
        temporary: Path | None = None
        try:
            root = Path(directory).resolve(strict=True)
            if not root.is_dir():
                raise OSError("export directory is not a directory")
            target = root / self.filename
            descriptor, name = tempfile.mkstemp(prefix=".export-", suffix=".tmp", dir=root)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(self.content)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, target)
            return target
        except FileExistsError as exc:
            raise ExportFileExistsError("export destination already exists") from exc
        except OSError as exc:
            raise ExportWriteError("could not save export in the supplied directory") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
