"""Explicit selection/DTO boundary; no normalization and no Engine imports."""

from collections.abc import Mapping

from .errors import InvalidExportInput
from .models import FIELD_NAMES, ExportRecord, NormalizedRecord


def from_normalized(record: NormalizedRecord) -> ExportRecord:
    """Read only the seven normalized fields without altering the source."""
    try:
        return ExportRecord(**{key: getattr(record, key) for key in FIELD_NAMES})
    except AttributeError as exc:
        raise InvalidExportInput("normalized object must expose all seven fields") from exc


def from_service_result(record: Mapping[str, object]) -> ExportRecord:
    """Adapt the BusinessResult mapping; ignore source/metadata and other keys."""
    if not isinstance(record, Mapping) or "name" not in record:
        raise InvalidExportInput("service result must be a mapping containing name")
    return ExportRecord(**{key: record.get(key) for key in FIELD_NAMES})
