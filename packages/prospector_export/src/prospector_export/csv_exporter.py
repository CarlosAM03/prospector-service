"""Adapted from frozen CLI exporters/csv.py: same schema and csv.writer dialect."""

import csv
import io
from collections.abc import Iterable

from ._serialization import LimitedBuffer, csv_text, validated_rows
from .models import HEADERS, ExportLimits, ExportRecord


def render_csv(records: Iterable[ExportRecord], limits: ExportLimits) -> bytes:
    output = LimitedBuffer(limits.max_output_bytes)
    row_buffer = io.StringIO(newline="")
    writer = csv.writer(row_buffer)

    def append(values: Iterable[str]) -> None:
        row_buffer.seek(0)
        row_buffer.truncate()
        writer.writerow(values)
        output.write(row_buffer.getvalue().encode("utf-8"))

    append(HEADERS)
    for row in validated_rows(records, limits):
        append(csv_text(value) for value in row)
    return output.getvalue()
