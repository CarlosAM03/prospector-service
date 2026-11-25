from dataclasses import asdict
from types import SimpleNamespace

import pytest
from prospector_engine import (
    Business,
    EngineConfig,
    NormalizedBusiness,
    ProspectorConfigurationError,
    SearchQuery,
    SearchResult,
    Source,
    SourceIdentityEvidence,
    VerificationState,
    VerifiedSourceIdentity,
)

from prospector_service.adapters import engine as module
from prospector_service.adapters.engine import execute_batch
from prospector_service.adapters.results import map_results
from prospector_service.errors import EngineExecutionError
from prospector_service.schemas import BatchRequest, ProspectingQuery


def query():
    return ProspectingQuery(source="google_maps", keyword="cafes", location="Tijuana", limit=2)


def result():
    request = SearchQuery(Source.GOOGLE_MAPS, "cafes", "Tijuana")
    verified = VerifiedSourceIdentity(Source.GOOGLE_MAPS, "google_place_id", "verified-pipeline-id")
    return SearchResult(
        request,
        businesses=[
            NormalizedBusiness(
                name="CAFE UNO",
                category="CAFE",
                address="TIJUANA",
                phone="664",
                email="INFO@example.com",
                website="https://example.com",
                language="ES",
            ),
            NormalizedBusiness(name="CAFE DOS"),
        ],
        original_businesses=[Business("Cafe Uno"), Business("Cafe Dos")],
        source_identities=(
            SourceIdentityEvidence(verified, VerificationState.VERIFIED, "fixture"),
            SourceIdentityEvidence.unverified(),
        ),
    )


def test_all_result_fields_identity_order_and_no_mutation():
    source = result()
    before = asdict(source)
    rows = map_results(source, query())
    assert rows[0].model_dump() == {
        "name": "CAFE UNO",
        "category": "CAFE",
        "address": "TIJUANA",
        "phone": "664",
        "email": "INFO@example.com",
        "website": "https://example.com",
        "language": "ES",
        "source": "google_maps",
        "sourceIdentifier": "verified-pipeline-id",
        "metadata": None,
    }
    assert rows[1].name == "CAFE DOS" and rows[1].sourceIdentifier is None
    assert rows[1].email is None and rows[1].metadata is None
    assert asdict(source) == before


def test_wrong_namespace_is_not_inferred():
    source = result()
    identity = VerifiedSourceIdentity(Source.GOOGLE_MAPS, "navigation_token", "not-a-place-id")
    source.source_identities = (
        SourceIdentityEvidence(identity, VerificationState.VERIFIED, "fixture"),
        SourceIdentityEvidence.unverified(),
    )
    assert map_results(source, query())[0].sourceIdentifier is None


def test_empty_result():
    empty = SearchResult(SearchQuery(Source.GOOGLE_MAPS, "cafes", "Tijuana"))
    assert map_results(empty, query()) == ()


@pytest.mark.parametrize("change", ["query", "alignment", "email", "website"])
def test_invalid_engine_result_fails_explicitly(change):
    source = result()
    if change == "query":
        source.query.keyword = "another-query"
    elif change == "alignment":
        source.source_identities = ()
    elif change == "email":
        source.businesses[0].email = "not-an-email"
    else:
        source.businesses[0].website = "javascript:alert(1)"
    with pytest.raises(EngineExecutionError, match="RESULT_MAPPING_FAILED"):
        map_results(source, query())


def test_execute_batch_uses_selected_indices_and_progress(monkeypatch):
    from prospector_engine import CancellationToken

    seen = []

    class Engine:
        def __init__(self, config):
            assert config.limit == 150

        def search_many(self, queries):
            assert [job.limit for job in queries] == [2, 2]
            return SimpleNamespace(
                entries=[
                    SimpleNamespace(
                        status=SimpleNamespace(value="partial"), result=result(), export_indices=[1]
                    ),
                    SimpleNamespace(status=SimpleNamespace(value="failed")),
                ]
            )

    def observe(listener):
        from contextlib import nullcontext

        listener(SimpleNamespace(stage="query", query_index=0, kind="execution_started"))
        listener(SimpleNamespace(stage="feed", query_index=None, kind="stage_started"))
        return nullcontext()

    monkeypatch.setattr(module, "ProspectorEngine", Engine)
    monkeypatch.setattr(module, "observe_execution", observe)
    batch = BatchRequest.model_validate(
        {
            "batchId": "c" + "1" * 24,
            "jobs": [{"jobId": "c" + str(i) * 24, "query": query()} for i in (2, 3)],
        }
    )
    execute_batch(batch, "chromium", True, CancellationToken(), seen.append)
    assert [item["type"] for item in seen] == ["running", "progress", "result"]
    assert seen[-1]["entries"][0]["quality"] == "PARTIAL"
    assert [row["name"] for row in seen[-1]["entries"][0]["rows"]] == ["CAFE DOS"]
    assert seen[-1]["entries"][1]["status"] == "FAILED"


@pytest.mark.integration
def test_real_installed_engine_batch_and_pin(monkeypatch):
    import json
    from importlib.metadata import distribution

    from prospector_engine import CancellationToken

    limits = []

    def source(request, limit, **options):
        limits.append(limit)
        return SimpleNamespace(
            query=request,
            businesses=[Business(" cafe ")],
            issues=[],
            identities=[SourceIdentityEvidence.unverified()],
        )

    monkeypatch.setattr("prospector_engine.engines.prospector_engine._run_google_maps", source)
    batch = BatchRequest.model_validate(
        {
            "batchId": "c" + "1" * 24,
            "jobs": [
                {"jobId": "c" + str(i) * 24, "query": query().model_copy(update={"limit": limit})}
                for i, limit in ((2, 150), (3, 1))
            ],
        }
    )
    events = []
    execute_batch(batch, "chromium", True, CancellationToken(), events.append)
    assert limits == [150, 1]
    assert [event["index"] for event in events if event["type"] == "running"] == [0, 1]
    assert all(entry["rows"][0]["name"] == "CAFE" for entry in events[-1]["entries"])
    direct = json.loads(distribution("prospector-engine").read_text("direct_url.json"))
    assert direct["vcs_info"]["commit_id"] == "030a82d63a499a8abe65352d282ccc9bbc076ff3"


@pytest.mark.integration
def test_real_engine_rejects_151_before_acquisition():
    from prospector_engine import BatchQuery, ProspectorEngine

    engine = ProspectorEngine(EngineConfig(limit=150))
    with pytest.raises(ProspectorConfigurationError):
        engine.search_many([BatchQuery(SearchQuery(Source.GOOGLE_MAPS, "cafe", "TJ"), 151)])


@pytest.mark.browser
def test_real_browser_smoke_without_external_network():
    from prospector_engine.browser import BrowserRuntime

    with BrowserRuntime(headless=True, channel=None) as runtime:
        page = runtime.new_page()
        page.set_content("<title>Prospector controlled browser</title>")
        assert page.title() == "Prospector controlled browser"
