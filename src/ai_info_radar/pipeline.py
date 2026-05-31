from __future__ import annotations

from pathlib import Path

from .extractors import ExtractionError, extract_items
from .fetchers import FetchError, fetch_source
from .manifest import load_sources
from .models import NormalizedItem, PollResult, SourcePollResult
from .store import RadarStore


UNDATED_INITIAL_BACKFILL_THRESHOLD = 10


def poll_sources(
    *,
    manifest_path: str | Path,
    db_path: str | Path,
    repo_root: str | Path,
    timeout_seconds: float = 10.0,
) -> PollResult:
    sources = load_sources(manifest_path)
    results: list[SourcePollResult] = []
    with RadarStore(db_path) as store:
        for source in sources:
            store.upsert_source(source)
            try:
                source_had_items = store.source_item_count(source.id) > 0
                fetched = fetch_source(source, repo_root=repo_root, timeout_seconds=timeout_seconds)
                items = extract_items(fetched)
                summary = store.insert_items(items)
            except (FetchError, ExtractionError, OSError) as exc:
                message = str(exc)
                store.record_health(source.id, ok=False, message=message, item_count=0)
                results.append(SourcePollResult(source_id=source.id, ok=False, message=message))
                continue

            message = f"提取到 {len(items)} 条"
            baselined = _baseline_initial_undated_backfill(
                store=store,
                source_had_items=source_had_items,
                items=items,
                inserted_item_ids=summary.inserted_item_ids,
            )
            if baselined:
                message += f"；已将 {baselined} 条无日期历史基线标记为已入日报"
            store.record_health(source.id, ok=True, message=message, item_count=len(items))
            results.append(
                SourcePollResult(
                    source_id=source.id,
                    ok=True,
                    inserted=summary.inserted,
                    existing=summary.existing,
                    message=message,
                )
            )
    return PollResult(results=results)


def _baseline_initial_undated_backfill(
    *,
    store: RadarStore,
    source_had_items: bool,
    items: list[NormalizedItem],
    inserted_item_ids: tuple[int, ...],
) -> int:
    if source_had_items:
        return 0
    if len(inserted_item_ids) <= UNDATED_INITIAL_BACKFILL_THRESHOLD:
        return 0
    if any(getattr(item, "published_at", None) for item in items):
        return 0
    return store.mark_new_items_daily(list(inserted_item_ids))
