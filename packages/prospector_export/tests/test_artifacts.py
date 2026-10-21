from concurrent.futures import ThreadPoolExecutor

import pytest

from prospector_export import (
    ExportArtifact,
    ExportFileExistsError,
    ExportFormat,
    ExportService,
    ExportWriteError,
    InvalidExportInput,
)


@pytest.mark.parametrize(
    "prefix", ["../../etc/evil", "x\r\nX-Evil: yes", "CON", "東京", "a" * 1000]
)
def test_safe_filename(prefix, tmp_path):
    artifact = ExportService.export([], "csv", filename_prefix=prefix)
    path = artifact.save(tmp_path)
    assert path.parent == tmp_path
    assert path.read_bytes() == artifact.content
    assert "/" not in artifact.filename and "\\" not in artifact.filename
    with pytest.raises(ExportFileExistsError):
        artifact.save(tmp_path)
    assert path.read_bytes() == artifact.content
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "filename",
    [
        "../a.csv",
        "a/b.csv",
        "a\\b.csv",
        "CON.csv",
        "a\r\n.csv",
        "LPT1.csv",
        ".a.csv",
        "a.xlsx",
        "a.csv:ads",
    ],
)
def test_artifact_rejects_unsafe_filenames(filename):
    with pytest.raises(InvalidExportInput):
        ExportArtifact(filename, ExportFormat.CSV.content_type, b"", ExportFormat.CSV)


def test_artifact_rejects_invalid_metadata():
    with pytest.raises(InvalidExportInput):
        ExportArtifact("safe.csv", "text/html", b"", ExportFormat.CSV)
    with pytest.raises(InvalidExportInput):
        ExportArtifact("safe.csv", ExportFormat.CSV.content_type, "", ExportFormat.CSV)


def test_write_failure_removes_partial_file(tmp_path, monkeypatch):
    artifact = ExportService.export([], "csv")

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("prospector_export.artifacts.os.fsync", fail)
    with pytest.raises(ExportWriteError) as error:
        artifact.save(tmp_path)
    assert isinstance(error.value.__cause__, OSError)
    assert list(tmp_path.iterdir()) == []


def test_link_failure_is_safe(tmp_path, monkeypatch):
    artifact = ExportService.export([], "csv")

    def fail(*args, **kwargs):
        raise OSError("hard links unavailable")

    monkeypatch.setattr("prospector_export.artifacts.os.link", fail)
    with pytest.raises(ExportWriteError):
        artifact.save(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_missing_directory_and_non_directory(tmp_path):
    artifact = ExportService.export([], "csv")
    with pytest.raises(ExportWriteError):
        artifact.save(tmp_path / "missing")
    file = tmp_path / "file"
    file.touch()
    with pytest.raises(ExportWriteError):
        artifact.save(file)


def test_concurrent_save_never_overwrites(tmp_path):
    artifact = ExportService.export([], "csv")

    def save():
        try:
            artifact.save(tmp_path)
            return True
        except ExportFileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: save(), range(4)))
    assert results.count(True) == 1
    assert list(tmp_path.iterdir()) == [tmp_path / artifact.filename]
