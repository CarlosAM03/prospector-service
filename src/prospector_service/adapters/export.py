from collections.abc import Iterable

from prospector_export import ExportArtifact, ExportFormat, ExportService, from_service_result

from ..schemas import BusinessResult


def export_results(records: Iterable[BusinessResult], format: ExportFormat | str) -> ExportArtifact:
    return ExportService.export(
        (from_service_result(record.model_dump()) for record in records),
        format,
    )
