from dataclasses import dataclass, fields
from typing import Protocol

from .errors import InvalidExportInput

HEADERS = ("Name", "Category", "Address", "Phone", "Email", "Website", "Language")
FIELD_NAMES = ("name", "category", "address", "phone", "email", "website", "language")


class NormalizedRecord(Protocol):
    """Structural read contract, independent from any Engine model."""

    @property
    def name(self) -> str: ...
    @property
    def category(self) -> str | None: ...
    @property
    def address(self) -> str | None: ...
    @property
    def phone(self) -> str | None: ...
    @property
    def email(self) -> str | None: ...
    @property
    def website(self) -> str | None: ...
    @property
    def language(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class ExportRecord:
    name: str
    category: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if not isinstance(value, str) and not (value is None and field.name != "name"):
                raise InvalidExportInput(f"{field.name} must be text or an optional null")


@dataclass(frozen=True, slots=True)
class ExportLimits:
    max_records: int = 10_000
    max_field_chars: int = 32_766
    max_input_bytes: int = 16 * 1024 * 1024
    max_output_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            minimum = 0 if field.name == "max_records" else 1
            if type(value) is not int or value < minimum:
                raise InvalidExportInput(f"{field.name} must be an integer >= {minimum}")
        if self.max_field_chars > 32_766:
            raise InvalidExportInput("max_field_chars must be <= 32766 for lossless XLSX")
        if self.max_records > 1_048_575:
            raise InvalidExportInput("max_records exceeds XLSX rows minus header")
