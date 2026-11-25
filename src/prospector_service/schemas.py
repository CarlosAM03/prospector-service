from datetime import datetime, timezone
from typing import Annotated, Literal

from email_validator import validate_email
from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

Cuid = Annotated[StrictStr, Field(pattern=r"^c[a-z0-9]{20,}$", max_length=128)]
JobStatus = Literal[
    "QUEUED", "RUNNING", "AWAITING_RESULTS", "COMPLETED", "FAILED", "INTERRUPTED", "SKIPPED"
]
Quality = Literal["SUCCESS", "SUCCESS_WITH_ISSUES", "PARTIAL"]
Availability = Literal["AVAILABLE", "EXPIRED", "PURGED", "UNAVAILABLE"]
Kind = Literal["STATE_CHANGED", "PROGRESS", "TERMINAL", "RESULT_AVAILABILITY_CHANGED"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProspectingQuery(DTO):
    keyword: StrictStr
    location: StrictStr
    source: Literal["google_maps"]
    limit: Annotated[StrictInt, Field(ge=1, le=150)]

    @field_validator("keyword", "location")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("invalid query text")
        value.encode("utf-8")
        return value


class JobRequest(DTO):
    jobId: Cuid
    query: ProspectingQuery


class BatchRequest(DTO):
    batchId: Cuid
    jobs: Annotated[tuple[JobRequest, ...], Field(min_length=1, max_length=5)]

    @model_validator(mode="after")
    def unique_ids(self):
        if len({job.jobId for job in self.jobs}) != len(self.jobs):
            raise ValueError("duplicate job IDs")
        return self


class AcceptedBatch(DTO):
    batchId: Cuid
    jobIds: Annotated[tuple[Cuid, ...], Field(min_length=1, max_length=5)]
    status: Literal["QUEUED"] = "QUEUED"
    acceptedAt: AwareDatetime


class BusinessResult(DTO):
    name: StrictStr
    source: Literal["google_maps"]
    category: StrictStr | None = None
    address: StrictStr | None = None
    phone: StrictStr | None = None
    email: StrictStr | None = Field(default=None, json_schema_extra={"format": "email"})
    website: StrictStr | None = Field(default=None, json_schema_extra={"format": "uri"})
    sourceIdentifier: StrictStr | None = None
    language: StrictStr | None = None
    metadata: dict | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value is not None:
            validate_email(value, check_deliverability=False, test_environment=True)
        return value

    @field_validator("website")
    @classmethod
    def valid_website(cls, value):
        if value is not None:
            AnyHttpUrl(value)
        return value


class ErrorBody(DTO):
    code: str
    message: str
    details: dict = Field(default_factory=dict)
    timestamp: AwareDatetime = Field(default_factory=utc_now)


class ErrorResponse(DTO):
    success: Literal[False] = False
    error: ErrorBody
