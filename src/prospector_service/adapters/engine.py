import math
from collections.abc import Callable

from prospector_engine import (
    BatchInterruptedError,
    BatchQuery,
    CancellationToken,
    EngineConfig,
    ProspectorEngine,
    SearchQuery,
    Source,
    cancellation_scope,
    observe_execution,
)

from ..schemas import BatchRequest
from .results import map_results

STAGES = {
    "query",
    "navigation",
    "feed",
    "detail",
    "details",
    "website",
    "website_enrichment",
    "normalization",
    "deduplication",
    "google_maps",
    "enrichment",
    "extraction",
    "runtime",
}
METRICS = {
    "requested_limit",
    "duplicates_suppressed",
    "exportable_businesses",
    "processed_businesses",
    "observed_businesses",
    "businesses_found",
}


def execute_batch(
    batch: BatchRequest, browser: str, headless: bool, token: CancellationToken, send: Callable
):
    cursor = None

    def observe(event):
        nonlocal cursor
        if event.stage == "query" and event.query_index is not None:
            if event.kind == "execution_started":
                cursor = event.query_index
                send({"type": "running", "index": cursor})
                return
            if event.kind in {"execution_completed", "execution_failed"}:
                send({"type": "awaiting", "index": cursor})
                cursor = None
                return
        if cursor is None or event.query_index not in {None, cursor}:
            return
        if event.kind in {"stage_started", "stage_completed"} and event.stage in STAGES:
            progress = {"kind": event.kind, "stage": event.stage}
        elif (
            event.kind == "metric_updated"
            and event.name in METRICS
            and type(event.value) in {int, float}
            and math.isfinite(event.value)
        ):
            progress = {"kind": event.kind, "name": event.name, "value": event.value}
        else:
            return
        send({"type": "progress", "index": cursor, "progress": progress})

    engine = ProspectorEngine(
        EngineConfig(
            limit=150, headless=headless, browser_channel="msedge" if browser == "msedge" else None
        )
    )
    queries = [
        BatchQuery(
            SearchQuery(Source.GOOGLE_MAPS, job.query.keyword, job.query.location), job.query.limit
        )
        for job in batch.jobs
    ]
    interrupted = None
    with cancellation_scope(token), observe_execution(observe):
        try:
            result = engine.search_many(queries)
        except BatchInterruptedError as exc:
            result = exc.completed
            interrupted = exc.interrupted_query_index

    entries = []
    for index, entry in enumerate(result.entries):
        if entry.status.value == "failed":
            entries.append({"status": "FAILED", "error": "ENGINE_QUERY_FAILED"})
            continue
        try:
            query = batch.jobs[index].query
            indices = entry.export_indices
            if len(indices) > query.limit:
                raise ValueError("result exceeds requested limit")
            rows = map_results(entry.result, query, indices)
            entries.append(
                {
                    "status": "COMPLETED",
                    "quality": entry.status.value.upper(),
                    "rows": [row.model_dump(mode="json") for row in rows],
                }
            )
        except Exception:
            entries.append({"status": "FAILED", "error": "RESULT_MAPPING_FAILED"})
    send({"type": "result", "entries": entries, "interrupted": interrupted})
