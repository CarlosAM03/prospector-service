from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

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

Cuid = Annotated[StrictStr, Field(pattern=r"^c[a-z0-9]{20,}$")]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ProspectingQuery(DTO):
    keyword: StrictStr
    location: StrictStr
    source: Literal["google_maps"]
    limit: Annotated[StrictInt, Field(ge=1, le=100)]

    @field_validator("keyword", "location")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query text must not be blank")
        return value


class StartJobRequest(DTO):
    jobId: Cuid
    tenantId: Cuid
    query: ProspectingQuery
    callbackUrl: StrictStr


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


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
            # Syntax only, no DNS. Preserve Engine's string rather than normalizing again.
            validate_email(value, check_deliverability=False, test_environment=True)
        return value

    @field_validator("website")
    @classmethod
    def valid_website(cls, value):
        if value is not None:
            AnyHttpUrl(value)
        return value


class PipelineProgress(DTO):
    source: Literal["google_maps"]
    stage: StrictStr
    message: StrictStr
    percentage: float = Field(ge=0, le=100, allow_inf_nan=False)


class JobEventError(DTO):
    code: str
    message: str


class JobEvent(DTO):
    eventId: UUID
    jobId: Cuid
    sequence: int = Field(ge=1)
    status: JobStatus
    progress: PipelineProgress | None
    timestamp: AwareDatetime
    results: tuple[BusinessResult, ...] | None
    error: JobEventError | None

    @model_validator(mode="after")
    def lifecycle_payload(self):
        if (self.status is JobStatus.COMPLETED) != (self.results is not None):
            raise ValueError("only COMPLETED events contain results (including empty results)")
        if (self.status is JobStatus.FAILED) != (self.error is not None):
            raise ValueError("only FAILED events contain error")
        if self.timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("timestamp must be UTC")
        return self


class AcceptedJob(DTO):
    jobId: Cuid
    status: Literal["QUEUED"] = "QUEUED"
    acceptedAt: AwareDatetime


class AcceptedJobResponse(DTO):
    success: Literal[True] = True
    data: AcceptedJob
    meta: dict = Field(default_factory=dict)


class ErrorBody(DTO):
    code: str
    message: str
    details: dict = Field(default_factory=dict)
    timestamp: AwareDatetime = Field(default_factory=utc_now)


class ErrorResponse(DTO):
    success: Literal[False] = False
    error: ErrorBody
