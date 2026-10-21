from prospector_engine import SearchResult, Source, VerificationState
from pydantic import ValidationError

from ..errors import EngineExecutionError
from ..schemas import BusinessResult, ProspectingQuery


def map_results(result: SearchResult, query: ProspectingQuery) -> tuple[BusinessResult, ...]:
    expected = (query.source, query.keyword, query.location)
    actual = (result.query.source.value, result.query.keyword, result.query.location)
    if actual != expected or len(result.businesses) != len(result.source_identities):
        raise EngineExecutionError("RESULT_MAPPING_FAILED")
    try:
        rows = []
        for business, evidence in zip(result.businesses, result.source_identities, strict=True):
            verified = evidence.verified
            identifier = None
            if (
                evidence.verification_state is VerificationState.VERIFIED
                and verified is not None
                and verified.source is Source.GOOGLE_MAPS
                and verified.kind == "google_place_id"
            ):
                identifier = verified.value
            rows.append(
                BusinessResult(
                    name=business.name,
                    category=business.category,
                    address=business.address,
                    phone=business.phone,
                    email=business.email,
                    website=business.website,
                    language=business.language,
                    source=query.source,
                    sourceIdentifier=identifier,
                    metadata=None,
                )
            )
        return tuple(rows)
    except (ValidationError, ValueError, AttributeError) as exc:
        raise EngineExecutionError("RESULT_MAPPING_FAILED") from exc
