from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from .config import load_focus, load_scoring, load_sources
from .fetchers import fetch_all
from .models import RadarItem, RadarRun, utc_now_iso
from .reporters import render_daily_radar
from .scoring import score_items
from .verification import verify_items


def run_daily_radar(
    sources_path: str | Path,
    focus_path: str | Path,
    scoring_path: str | Path,
    repo_root: str | Path,
    max_items: int = 15,
    max_age_days: int | None = None,
    max_per_source: int | None = None,
    timeout_seconds: float = 10.0,
) -> RadarRun:
    root = Path(repo_root)
    sources = load_sources(sources_path)
    focus = load_focus(focus_path)
    scoring = load_scoring(scoring_path)

    fetched = fetch_all(sources, root, timeout_seconds=timeout_seconds)
    deduped = deduplicate_items(fetched.items)
    recent = filter_by_max_age(deduped, max_age_days=max_age_days)
    scored = score_items(recent, focus, scoring)
    verified = verify_items(scored)
    ranked = sorted(verified, key=lambda item: item.final_score, reverse=True)
    clustered = cluster_similar_items(ranked)
    selected = select_ranked_items(clustered, max_items=max_items, max_per_source=max_per_source)
    return RadarRun(items=selected, fetch_errors=fetched.errors, generated_at=utc_now_iso())


def write_daily_radar(run: RadarRun, output_path: str | Path, language: str = "zh") -> str:
    report = render_daily_radar(run, language=language)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return report


def deduplicate_items(items: list[RadarItem]) -> list[RadarItem]:
    seen: dict[str, RadarItem] = {}
    for item in items:
        key = _dedupe_key(item)
        current = seen.get(key)
        if current is None or _source_rank(item.source_tier) > _source_rank(current.source_tier):
            seen[key] = item
    return list(seen.values())


def select_ranked_items(
    ranked_items: list[RadarItem],
    max_items: int,
    max_per_source: int | None = None,
) -> list[RadarItem]:
    if not max_per_source:
        return ranked_items[:max_items]

    selected: list[RadarItem] = []
    source_counts: dict[str, int] = {}
    for item in ranked_items:
        count = source_counts.get(item.source_name, 0)
        if count >= max_per_source:
            continue
        selected.append(item)
        source_counts[item.source_name] = count + 1
        if len(selected) >= max_items:
            break
    return selected


def filter_by_max_age(
    items: list[RadarItem],
    max_age_days: int | None = None,
    now: datetime | None = None,
) -> list[RadarItem]:
    if not max_age_days:
        return items
    reference = now or datetime.now(timezone.utc)
    kept: list[RadarItem] = []
    for item in items:
        published = _parse_datetime(item.published_time)
        if published is None:
            kept.append(item)
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = (reference - published.astimezone(timezone.utc)).days
        if age_days <= max_age_days:
            kept.append(item)
    return kept


def cluster_similar_items(ranked_items: list[RadarItem]) -> list[RadarItem]:
    clusters: dict[str, RadarItem] = {}
    ordered: list[RadarItem] = []
    for item in ranked_items:
        key = _cluster_key(item)
        representative = clusters.get(key)
        if representative is None:
            item.related_items = []
            clusters[key] = item
            ordered.append(item)
            continue
        representative.related_items.append(item)
    return ordered


def _dedupe_key(item: RadarItem) -> str:
    if item.url:
        return item.url.strip().lower().rstrip("/")
    return "title:" + " ".join(item.title.lower().split())


def _cluster_key(item: RadarItem) -> str:
    source = item.source_name.lower()
    text = item.text_for_matching
    title = item.title.lower()

    if source == "openai agents python releases":
        return "openai-agents:release"

    if source == "openai python sdk releases":
        return "openai-python-sdk:release"

    if source == "anthropic python sdk releases":
        return "anthropic-python-sdk:release"

    if source == "openai news" and "codex" in text:
        return "openai-news:codex-adoption"

    if source == "browser use releases":
        if "cli" in text or "cdp" in text:
            return "browser-use:cli-cdp"
        return "browser-use:release"

    if source.startswith("mcp "):
        return "mcp:release"

    if source.startswith("arxiv"):
        if "energy" in text or "battery" in text or "early termination" in text:
            return "paper:agent-efficiency"
        if "self-critique" in text or _has_word(text, "critic"):
            return "paper:self-improvement"
        if "authorization" in text or "security" in text or "sovereign" in text:
            return "paper:agent-security"
        if "multi-agent" in text:
            return "paper:multi-agent"
        if "quantization" in text or "bias" in text or "alignment" in text:
            return "paper:model-compression-risk"
        if "scaffolding" in text or "collaboration" in text:
            return "paper:human-llm-collaboration"
        if "agent" in text:
            return "paper:agent-systems"
        return "paper:other"

    return f"{source}:{item.id}"


def _source_rank(tier: str) -> int:
    return {"primary": 3, "strong_signal": 2, "lead": 1}.get(tier, 0)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _has_word(text: str, word: str) -> bool:
    return f" {word} " in f" {text} "
