"""Optional HTTP boundary. Importing the core never imports this module."""

from typing import TYPE_CHECKING

from .artifacts import ExportArtifact
from .errors import MissingExportDependency

if TYPE_CHECKING:
    from fastapi import Response


def to_response(artifact: ExportArtifact) -> "Response":
    """Return a bounded in-memory download; register no routes or authentication."""
    try:
        from fastapi import Response
    except ImportError as exc:
        raise MissingExportDependency(
            "HTTP adapter requires pip install 'prospector-export[fastapi]'"
        ) from exc
    return Response(
        content=artifact.content,
        headers={
            "Content-Type": artifact.content_type,
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
