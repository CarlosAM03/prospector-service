from dataclasses import asdict
from types import SimpleNamespace

import pytest
from prospector_engine import (
    Business,
    EngineConfig,
    NormalizedBusiness,
    ProspectorConfigurationError,
    ProspectorExtractionError,
    ProspectorNavigationError,
    ProspectorRuntimeError,
    ProspectorSourceError,
    SearchQuery,
    SearchResult,
    Source,
    SourceIdentityEvidence,
    VerificationState,
    VerifiedSourceIdentity,
)

from prospector_service.adapters import engine as module
from prospector_service.adapters.engine import EngineAdapter
from prospector_service.adapters.results import map_results
from prospector_service.errors import EngineExecutionError
from prospector_service.schemas import ProspectingQuery


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


def test_engine_adapter_uses_public_query_config(settings, monkeypatch):
    seen = {}

    class Spy:
        def __init__(self, config):
            seen["config"] = config

        def search(self, request):
            seen["query"] = request
            return result()

    monkeypatch.setattr(module, "ProspectorEngine", Spy)
    adapter = EngineAdapter(settings)
    mapped = adapter.execute(query(), adapter.new_token())
    assert mapped[0].name == "CAFE UNO"
    assert seen["config"] == EngineConfig(limit=2, headless=False, browser_channel="msedge")
    assert seen["query"] == SearchQuery(Source.GOOGLE_MAPS, "cafes", "Tijuana")


@pytest.mark.parametrize(
    "error,code,runtime",
    [
        (ProspectorConfigurationError, "ENGINE_CONFIGURATION_ERROR", False),
        (ProspectorSourceError, "ENGINE_SOURCE_UNSUPPORTED", False),
        (ProspectorNavigationError, "ENGINE_NAVIGATION_FAILED", False),
        (ProspectorExtractionError, "ENGINE_EXTRACTION_FAILED", False),
        (ProspectorRuntimeError, "ENGINE_RUNTIME_UNAVAILABLE", True),
    ],
)
def test_typed_engine_errors(settings, monkeypatch, error, code, runtime):
    class Spy:
        def __init__(self, config):
            pass

        def search(self, request):
            raise error("private details must not escape")

    monkeypatch.setattr(module, "ProspectorEngine", Spy)
    adapter = EngineAdapter(settings)
    with pytest.raises(EngineExecutionError) as failure:
        adapter.execute(query(), adapter.new_token())
    assert failure.value.code == code and failure.value.runtime_unavailable is runtime
    assert "private" not in str(failure.value)


def test_unexpected_engine_error_remains_detectable(settings, monkeypatch):
    class Spy:
        def __init__(self, config):
            raise LookupError("controlled")

    monkeypatch.setattr(module, "ProspectorEngine", Spy)
    adapter = EngineAdapter(settings)
    with pytest.raises(LookupError):
        adapter.execute(query(), adapter.new_token())


@pytest.mark.integration
def test_real_installed_engine_pipeline_with_controlled_source(settings, monkeypatch):
    # Only this offline test replaces the private acquisition seam in memory.
    # Actual installed public facade, global normalization, models, and mapping execute.
    def source(request, limit, **options):
        return SimpleNamespace(
            query=request,
            businesses=[Business(" cafe ")],
            issues=[],
            identities=[SourceIdentityEvidence.unverified()],
        )

    monkeypatch.setattr("prospector_engine.engines.prospector_engine._run_google_maps", source)
    adapter = EngineAdapter(settings)
    rows = adapter.execute(query(), adapter.new_token())
    assert rows[0].name == "CAFE" and rows[0].sourceIdentifier is None


@pytest.mark.integration
def test_real_package_public_preflight_without_network():
    import importlib.metadata
    import inspect

    from prospector_engine import ProspectorEngine

    engine = ProspectorEngine(EngineConfig(limit=101))
    with pytest.raises(ProspectorConfigurationError):
        engine.search(SearchQuery(Source.GOOGLE_MAPS, "cafe", "Tijuana"))
    assert str(inspect.signature(ProspectorEngine.search)).startswith("(self, query:")
    distribution = importlib.metadata.distribution("prospector-engine")
    assert distribution.version == "0.1.0.dev0"
    import json

    direct = json.loads(distribution.read_text("direct_url.json"))
    assert direct["vcs_info"]["commit_id"] == "70f6081688db5c5bc5ea612f5fabd5724aab0b20"


@pytest.mark.browser
def test_real_browser_readiness_probe_without_external_network(settings):
    adapter = EngineAdapter(
        settings.model_copy(
            update={
                "engine_browser": "chromium",
                "engine_headless": True,
            }
        )
    )
    assert adapter.probe()
