import csv
import io
from dataclasses import asdict

import pytest

from prospector_export import (
    HEADERS,
    ExportFormat,
    ExportLimitExceeded,
    ExportLimits,
    ExportRecord,
    ExportService,
    InvalidExportInput,
    UnsupportedExportFormat,
)

FORMATS = [ExportFormat.CSV, ExportFormat.XLSX]


def read_rows(artifact):
    if artifact.format is ExportFormat.CSV:
        return list(csv.reader(io.StringIO(artifact.content.decode("utf-8"), newline="")))
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.load_workbook(artifact.open_binary(), read_only=True)
    try:
        assert workbook.sheetnames == ["Businesses"]
        return [list(row) for row in workbook["Businesses"].values]
    finally:
        workbook.close()


@pytest.mark.parametrize("format", FORMATS)
def test_frozen_schema_values_and_no_mutation(format, tmp_path, monkeypatch):
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    monkeypatch.chdir(tmp_path)
    record = ExportRecord(
        "EXAMPLE CAFE",
        "CAFE",
        "Main Street",
        "555 123 4567",
        "info@example.test",
        "https://example.test",
        "ES",
    )
    records = [record, ExportRecord("CAFE DOS")]
    before = [asdict(item) for item in records]
    artifact = ExportService.export(records, format)
    rows = read_rows(artifact)
    assert rows[0] == list(HEADERS)
    assert rows[1] == list(asdict(record).values())
    assert rows[2] == ["CAFE DOS"] + ([""] if format is ExportFormat.CSV else [None]) * 6
    assert [asdict(item) for item in records] == before
    assert not list(tmp_path.iterdir())
    assert artifact.format is format
    assert artifact.content_type == format.content_type
    assert artifact.filename.endswith("." + format.value)
    assert isinstance(artifact.content, bytes)
    with artifact.open_binary() as stream:
        assert stream.read() == artifact.content


@pytest.mark.parametrize("format", FORMATS)
def test_zero_records(format):
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    assert read_rows(ExportService.export([], format)) == [list(HEADERS)]


@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize(
    "text",
    [
        'CAFÉ 東京 😀, "UNO";DOS',
        "Calle uno\nInterior dos",
        "a\rb",
        "a\tb",
        "",
        "#N/A",
        "001234",
        "https://example.test/?x=1&y=2",
        "A" * 32766,
    ],
    ids=lambda value: f"text-{len(value)}",
)
def test_text_integrity(format, text):
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    rows = read_rows(ExportService.export([ExportRecord(text)], format))
    # openpyxl reads a serialized empty string as a blank cell, as did the CLI.
    expected = None if format is ExportFormat.XLSX and text == "" else text
    assert rows[1][0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "=1+1",
        "+SUM(1,2)",
        "-1+2",
        "@SUM(1)",
        " \t=1",
        "\tHi",
        "\rHi",
        "\nHi",
        "＝1+1",
        "＋1",
        "－1",
        "＠A",
        '=HYPERLINK("https://example.test")',
    ],
)
def test_formula_safety(text):
    record = ExportRecord(text, text, text, text, text, text, text)
    assert read_rows(ExportService.export([record], "csv"))[1] == ["'" + text] * 7
    openpyxl = pytest.importorskip("openpyxl")
    artifact = ExportService.export([record], "xlsx")
    workbook = openpyxl.load_workbook(artifact.open_binary())
    try:
        for cell in workbook["Businesses"][2]:
            assert cell.value == text and cell.data_type == "s"
            assert cell.hyperlink is None
    finally:
        workbook.close()
    assert record.name == text


@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize("text", ["\x00", "\x01", "\x0b", "\ud800", "\ufffe", "\uffff"])
def test_unsupported_characters_are_rejected_without_loss(format, text):
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    with pytest.raises(InvalidExportInput):
        ExportService.export([ExportRecord(text)], format)


@pytest.mark.parametrize("format", FORMATS)
@pytest.mark.parametrize(
    "limits,records",
    [
        (ExportLimits(max_records=1), [ExportRecord("A"), ExportRecord("B")]),
        (ExportLimits(max_field_chars=1), [ExportRecord("AA")]),
        (ExportLimits(max_input_bytes=1), [ExportRecord("é")]),
        (ExportLimits(max_output_bytes=1), []),
    ],
)
def test_configured_limits(format, limits, records):
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    with pytest.raises(ExportLimitExceeded):
        ExportService.export(iter(records), format, limits=limits)


def test_record_limit_bounds_generator_consumption():
    seen = []

    def records():
        for index in range(100):
            seen.append(index)
            yield ExportRecord(str(index))

    with pytest.raises(ExportLimitExceeded):
        ExportService.export(records(), "csv", limits=ExportLimits(max_records=2))
    assert seen == [0, 1, 2]


@pytest.mark.parametrize("records", [None, 1, "abc", [{"name": "A"}], [object()]])
def test_invalid_records(records):
    with pytest.raises(InvalidExportInput):
        ExportService.export(records, "csv")


@pytest.mark.parametrize("format", [None, 1, "excel", "CSV", "pdf", ""])
def test_invalid_format(format):
    with pytest.raises(UnsupportedExportFormat):
        ExportService.export([], format)


@pytest.mark.parametrize(
    "options",
    [
        {"max_records": -1},
        {"max_records": True},
        {"max_records": 1_048_576},
        {"max_field_chars": 32767},
        {"max_output_bytes": 0},
        {"max_input_bytes": 1.5},
    ],
)
def test_invalid_limits(options):
    with pytest.raises(InvalidExportInput):
        ExportLimits(**options)


def test_invalid_options_and_fields():
    with pytest.raises(InvalidExportInput):
        ExportRecord(None)
    with pytest.raises(InvalidExportInput):
        ExportRecord("A", phone=123)
    with pytest.raises(InvalidExportInput):
        ExportService.export([], "csv", limits={})
    with pytest.raises(InvalidExportInput):
        ExportService.export([], "csv", filename_prefix=None)


def test_default_large_record_count_is_bounded():
    with pytest.raises(ExportLimitExceeded, match="max_records"):
        ExportService.export((ExportRecord("A") for _ in range(10_001)), "csv")


@pytest.mark.parametrize("format", FORMATS)
def test_explicit_batch_selections_keep_order_and_duplicates(format):
    if format is ExportFormat.XLSX:
        pytest.importorskip("openpyxl")
    records = [ExportRecord("CAFE UNO"), ExportRecord("CAFE DOS")]
    first = ExportService.export(
        [records[1], records[0], records[1]], format, filename_prefix="batch_a_q01"
    )
    second = ExportService.export([], format, filename_prefix="batch_a_q02")
    third = ExportService.export([], format, filename_prefix="batch_a_q02")
    assert [row[0] for row in read_rows(first)[1:]] == ["CAFE DOS", "CAFE UNO", "CAFE DOS"]
    assert read_rows(second) == [list(HEADERS)]
    assert len({first.filename, second.filename, third.filename}) == 3
    assert [record.name for record in records] == ["CAFE UNO", "CAFE DOS"]
