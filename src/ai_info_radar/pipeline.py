from __future__ import annotations

from pathlib import Path

from .extractors import ExtractionError, extract_items
from .fetchers import FetchError, fetch_source
from .manifest import load_sources
from .models import PollResult, SourcePollResult
from .store import RadarStore


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
                fetched = fetch_source(source, repo_root=repo_root, timeout_seconds=timeout_seconds)
                items = extract_items(fetched)
                summary = store.insert_items(items)
            except (FetchError, ExtractionError, OSError) as exc:
                message = str(exc)
                store.record_health(source.id, ok=False, message=message, item_count=0)
                results.append(SourcePollResult(source_id=source.id, ok=False, message=message))
                continue

            message = f"{len(items)} item(s) extracted"
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
