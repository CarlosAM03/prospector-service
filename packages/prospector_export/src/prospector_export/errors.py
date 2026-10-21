"""Stable errors for consumers; original I/O failures are chained."""


class ExportError(Exception):
    """Base export error."""


class InvalidExportInput(ExportError, ValueError):
    """Invalid record, option, filename or character."""


class UnsupportedExportFormat(InvalidExportInput):
    """Only canonical csv and xlsx are supported."""


class ExportLimitExceeded(ExportError):
    """A configured resource limit was exceeded."""


class MissingExportDependency(ExportError, ImportError):
    """An optional extra is required."""


class ExportWriteError(ExportError, OSError):
    """Serialization or filesystem write failed."""


class ExportFileExistsError(ExportWriteError, FileExistsError):
    """The destination exists; it was not replaced."""
