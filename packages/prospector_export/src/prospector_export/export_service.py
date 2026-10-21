import re
from collections.abc import Iterable
from uuid import uuid4

from .artifacts import ExportArtifact
from .csv_exporter import render_csv
from .errors import ExportWriteError, InvalidExportInput
from .formats import ExportFormat
from .models import ExportLimits, ExportRecord


class ExportService:
    @staticmethod
    def export(
        records: Iterable[ExportRecord],
        format: ExportFormat | str,
        *,
        filename_prefix: str = "businesses",
        limits: ExportLimits | None = None,
    ) -> ExportArtifact:
        selected = ExportFormat.parse(format)
        if not isinstance(filename_prefix, str):
            raise InvalidExportInput("filename_prefix must be text")
        if limits is None:
            limits = ExportLimits()
        elif not isinstance(limits, ExportLimits):
            raise InvalidExportInput("limits must be ExportLimits")
        prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", filename_prefix).strip("_-")[:64]
        filename = f"{prefix or 'businesses'}_{uuid4().hex}.{selected.value}"
        try:
            if selected is ExportFormat.CSV:
                content = render_csv(records, limits)
            else:
                from .xlsx_exporter import render_xlsx

                content = render_xlsx(records, limits)
        except (OSError, UnicodeError) as exc:
            raise ExportWriteError("export serialization failed") from exc
        return ExportArtifact(filename, selected.content_type, content, selected)
