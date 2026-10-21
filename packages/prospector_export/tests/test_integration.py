import ast
import builtins
import dataclasses
import importlib.metadata
import subprocess
import sys
from pathlib import Path

import pytest

from prospector_export import (
    ExportFormat,
    ExportRecord,
    ExportService,
    InvalidExportInput,
    MissingExportDependency,
    from_normalized,
    from_service_result,
)


@dataclasses.dataclass
class NormalizedFixture:
    name: str = "CAFE UNO"
    category: str | None = "CAFE"
    address: str | None = "TIJUANA"
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    language: str | None = "ES"
    metadata: dict = dataclasses.field(default_factory=lambda: {"original": "Cafe Uno"})


def test_normalized_adapter_no_mutation():
    source = NormalizedFixture()
    before = dataclasses.asdict(source)
    record = from_normalized(source)
    assert record == ExportRecord("CAFE UNO", "CAFE", "TIJUANA", language="ES")
    assert dataclasses.asdict(source) == before
    assert not hasattr(record, "metadata")
    with pytest.raises(InvalidExportInput):
        from_normalized(object())


def test_service_result_adapter():
    source = {"name": "CAFE UNO", "source": "google_maps", "metadata": {"tenant": "a"}}
    assert from_service_result(source) == ExportRecord("CAFE UNO")
    assert source["metadata"] == {"tenant": "a"}
    with pytest.raises(InvalidExportInput):
        from_service_result({})


def test_architecture_imports():
    root = Path(importlib.metadata.distribution("prospector-export").locate_file(""))
    import prospector_export

    root = Path(prospector_export.__file__).parent
    forbidden = {
        "rich",
        "playwright",
        "bs4",
        "prospector_engine",
        "prisma",
        "models",
        "engines",
        "services",
        "exporters",
    }
    for file in root.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] in forbidden for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] not in forbidden
    requirements = importlib.metadata.requires("prospector-export") or []
    assert all("extra ==" in item for item in requirements)


@pytest.mark.integration
def test_external_process_does_not_import_optional_dependencies(tmp_path):
    script = """
import sys
from prospector_export import ExportService, ExportRecord
artifact = ExportService.export([ExportRecord('CAFÉ')], 'csv')
assert 'CAFÉ' in artifact.content.decode('utf-8')
assert not any(x in sys.modules for x in ('openpyxl', 'fastapi', 'prospector_engine', 'rich'))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_missing_optional_dependencies(monkeypatch):
    original = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name in {"openpyxl", "fastapi"}:
            raise ModuleNotFoundError(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    assert ExportService.export([], "csv").content
    with pytest.raises(MissingExportDependency, match="xlsx"):
        ExportService.export([], "xlsx")
    from prospector_export.fastapi_adapter import to_response

    with pytest.raises(MissingExportDependency, match="fastapi"):
        to_response(ExportService.export([], "csv"))


@pytest.mark.integration
@pytest.mark.parametrize("format", [ExportFormat.CSV, ExportFormat.XLSX])
def test_fastapi_response_with_fixture(format):
    fastapi = pytest.importorskip("fastapi")
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    from fastapi.testclient import TestClient

    from prospector_export.fastapi_adapter import to_response

    app = fastapi.FastAPI()
    artifact = ExportService.export([from_normalized(NormalizedFixture())], format)

    @app.get("/fixture-download")
    def download():
        return to_response(artifact)

    with TestClient(app) as client:
        response = client.get("/fixture-download")
    assert response.status_code == 200
    assert response.content == artifact.content
    assert response.headers["content-type"] == format.content_type
    assert response.headers["content-disposition"] == f'attachment; filename="{artifact.filename}"'
    assert response.headers["cache-control"] == "no-store"
