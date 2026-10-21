from enum import Enum

from .errors import UnsupportedExportFormat


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"

    @property
    def content_type(self) -> str:
        if self is ExportFormat.CSV:
            return "text/csv; charset=utf-8"
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @classmethod
    def parse(cls, value: object) -> "ExportFormat":
        if not isinstance(value, str):
            raise UnsupportedExportFormat("format must be 'csv' or 'xlsx'")
        try:
            return cls(value)
        except ValueError as exc:
            raise UnsupportedExportFormat("format must be 'csv' or 'xlsx'") from exc
