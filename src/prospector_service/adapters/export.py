from collections.abc import Iterable

from prospector_export import (
    ExportArtifact,
    ExportFormat,
    ExportLimits,
    ExportService,
    from_service_result,
)

from ..schemas import BusinessResult


def export_results(
    records: Iterable[BusinessResult], format: ExportFormat | str, *, max_bytes: int = 4194304
) -> ExportArtifact:
    return ExportService.export(
        (from_service_result(record.model_dump()) for record in records),
        format,
        limits=ExportLimits(max_records=150, max_output_bytes=max_bytes),
    )
