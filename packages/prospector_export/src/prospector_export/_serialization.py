import io
import re
from collections.abc import Iterable, Iterator

from .errors import ExportLimitExceeded, InvalidExportInput
from .models import FIELD_NAMES, ExportLimits, ExportRecord

_INVALID_TEXT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


class LimitedBuffer(io.BytesIO):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit

    def write(self, data: bytes) -> int:
        if self.tell() + len(data) > self.limit:
            raise ExportLimitExceeded("max_output_bytes exceeded")
        return super().write(data)


def validated_rows(
    records: Iterable[ExportRecord], limits: ExportLimits
) -> Iterator[tuple[str | None, ...]]:
    try:
        iterator = iter(records)
    except TypeError as exc:
        raise InvalidExportInput("records must be an iterable of ExportRecord") from exc
    total_bytes = 0
    for index, record in enumerate(iterator):
        if index >= limits.max_records:
            raise ExportLimitExceeded("max_records exceeded")
        if not isinstance(record, ExportRecord):
            raise InvalidExportInput("records must contain ExportRecord; use an explicit adapter")
        row = tuple(getattr(record, key) for key in FIELD_NAMES)
        for value in row:
            if value is None:
                continue
            if len(value) > limits.max_field_chars:
                raise ExportLimitExceeded("max_field_chars exceeded")
            if _INVALID_TEXT.search(value):
                raise InvalidExportInput("text contains unsupported control or Unicode characters")
            total_bytes += len(value.encode("utf-8"))
            if total_bytes > limits.max_input_bytes:
                raise ExportLimitExceeded("max_input_bytes exceeded")
        yield row


def csv_text(value: str | None) -> str:
    if value is None:
        return ""
    # Guard whitespace-prefixed formulas and leading spreadsheet control characters.
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(
        ("=", "+", "-", "@", "＝", "＋", "－", "＠")
    ):
        return "'" + value
    return value
