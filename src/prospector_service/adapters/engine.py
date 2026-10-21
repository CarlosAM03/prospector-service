import logging

from prospector_engine import (
    CancellationRequested,
    CancellationToken,
    EngineConfig,
    ExecutionEvent,
    ProspectorConfigurationError,
    ProspectorEngine,
    ProspectorError,
    ProspectorExtractionError,
    ProspectorNavigationError,
    ProspectorRuntimeError,
    ProspectorSourceError,
    SearchQuery,
    Source,
    cancellation_scope,
    observe_execution,
)

from ..config import Settings
from ..errors import EngineCancelled, EngineExecutionError
from ..schemas import BusinessResult, ProspectingQuery
from .results import map_results

logger = logging.getLogger(__name__)


class EngineAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def new_token(self) -> CancellationToken:
        return CancellationToken()

    def _config(self, limit: int) -> EngineConfig:
        return EngineConfig(
            limit=limit,
            headless=self.settings.engine_headless,
            browser_channel="msedge" if self.settings.engine_browser == "msedge" else None,
        )

    def probe(self) -> bool:
        try:
            from prospector_engine.browser import BrowserRuntime

            config = self._config(1)
            ProspectorEngine(config)
            with BrowserRuntime(
                headless=config.headless, channel=config.browser_channel
            ) as runtime:
                page = runtime.new_page()
                page.set_content("<html><title>Prospector readiness</title></html>")
                return page.title() == "Prospector readiness"
        except Exception:
            logger.warning("engine_probe_failed")
            return False

    def execute(
        self, query: ProspectingQuery, token: CancellationToken
    ) -> tuple[BusinessResult, ...]:
        def observed(event: ExecutionEvent) -> None:
            # No query/business text, raw exception, URL or credentials in Service logs.
            logger.info(
                "engine_event", extra={"engine_kind": event.kind, "engine_stage": event.stage}
            )

        try:
            engine = ProspectorEngine(self._config(query.limit))
            request = SearchQuery(Source.GOOGLE_MAPS, query.keyword, query.location)
            with cancellation_scope(token), observe_execution(observed):
                token.raise_if_cancelled()
                return map_results(engine.search(request), query)
        except CancellationRequested as exc:
            raise EngineCancelled() from exc
        except ProspectorRuntimeError as exc:
            raise EngineExecutionError(
                "ENGINE_RUNTIME_UNAVAILABLE", runtime_unavailable=True
            ) from exc
        except ProspectorConfigurationError as exc:
            raise EngineExecutionError("ENGINE_CONFIGURATION_ERROR") from exc
        except ProspectorSourceError as exc:
            raise EngineExecutionError("ENGINE_SOURCE_UNSUPPORTED") from exc
        except ProspectorNavigationError as exc:
            raise EngineExecutionError("ENGINE_NAVIGATION_FAILED") from exc
        except ProspectorExtractionError as exc:
            raise EngineExecutionError("ENGINE_EXTRACTION_FAILED") from exc
        except ProspectorError as exc:
            raise EngineExecutionError("ENGINE_EXECUTION_FAILED") from exc
