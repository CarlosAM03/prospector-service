"""Adapted from frozen CLI exporters/excel.py; openpyxl is loaded only on use."""

from collections.abc import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from ._serialization import LimitedBuffer, validated_rows
from .errors import MissingExportDependency
from .models import HEADERS, ExportLimits, ExportRecord


def render_xlsx(records: Iterable[ExportRecord], limits: ExportLimits) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.writer.excel import ExcelWriter
    except ImportError as exc:
        raise MissingExportDependency(
            "XLSX requires pip install 'prospector-export[xlsx]'"
        ) from exc

    workbook = Workbook()
    try:
        sheet = workbook.active
        sheet.title = "Businesses"
        sheet.append(HEADERS)
        has_carriage_return = False
        for row_index, row in enumerate(validated_rows(records, limits), start=2):
            for col_index, value in enumerate(row, start=1):
                cell = sheet.cell(row_index, col_index, value)
                if value is not None:
                    has_carriage_return |= "\r" in value
                    # Explicit string cells prevent formulas and Excel error coercion.
                    cell.data_type = "s"
        output = LimitedBuffer(limits.max_output_bytes)
        # Own the archive so an output-limit exception still closes ZIP resources.
        with ZipFile(output, "w", ZIP_DEFLATED, allowZip64=True) as archive:
            ExcelWriter(workbook, archive).save()
        if has_carriage_return:
            # ElementTree/et_xmlfile emits literal CR, which XML readers normalize.
            # Character references preserve it without changing business values.
            corrected = LimitedBuffer(limits.max_output_bytes)
            output.seek(0)
            with ZipFile(output) as source, ZipFile(corrected, "w") as target:
                for entry in source.infolist():
                    with source.open(entry) as original, target.open(entry, "w") as destination:
                        while chunk := original.read(64 * 1024):
                            if entry.filename.startswith("xl/worksheets/"):
                                chunk = chunk.replace(b"\r", b"&#13;")
                            destination.write(chunk)
            return corrected.getvalue()
        return output.getvalue()
    finally:
        workbook.close()
