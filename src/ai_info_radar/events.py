from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .classifier import KEYWORD_RULES
from .models import EventRecord, StoredItem
from .store import RadarStore


COOLDOWN_HOURS = 72
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref"}


def merge_events(store: RadarStore, *, cooldown_hours: int = COOLDOWN_HOURS) -> list[EventRecord]:
    for item in store.list_items():
        match_keys = hard_match_keys(item)
        event_key = store.find_event_by_match_keys(match_keys)
        matched_by = "hard" if event_key else "new"

        if event_key is None:
            event_key = _find_approximate_event(store.list_events(), item, cooldown_hours)
            matched_by = "approximate" if event_key else "new"

        if event_key is None:
            event_key = _new_event_key(item)

        store.upsert_event_item(
            event_key=event_key,
            item=item,
            relation="canonical" if matched_by == "new" else "supporting",
            matched_by=matched_by,
        )
        store.register_event_match_keys(event_key=event_key, match_keys=match_keys)

    return store.list_events()


def hard_match_keys(item: StoredItem) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for url in _candidate_urls(item):
        canonical = canonicalize_url(url)
        if canonical:
            keys.append((f"url:{canonical}", "canonical_url"))
        release_key = _github_release_key(canonical)
        if release_key:
            keys.append((f"github-release:{release_key}", "github_release_tag"))

    feed_id = _trace_string(item, "feed_id")
    if feed_id:
        keys.append((f"feed-id:{item.source_id}:{feed_id}", "feed_id"))

    source_item_id = _trace_string(item, "source_item_id")
    if source_item_id:
        keys.append((f"source-item:{item.source_id}:{source_item_id}", "source_item_id"))

    return list(dict.fromkeys(keys))


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_QUERY_KEYS and not key.startswith(TRACKING_QUERY_PREFIXES)
    ]
    path = parsed.path.rstrip("/") or parsed.path
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(query, doseq=True),
            parsed.fragment,
        )
    )


def _candidate_urls(item: StoredItem) -> tuple[str, ...]:
    urls = [item.url]
    target_url = _trace_string(item, "target_url")
    if target_url:
        urls.append(target_url)
    canonical_url = _trace_string(item, "canonical_url")
    if canonical_url:
        urls.append(canonical_url)
    return tuple(urls)


def _find_approximate_event(
    events: list[EventRecord],
    item: StoredItem,
    cooldown_hours: int,
) -> str | None:
    item_title = _normalize_title(item.title)
    item_terms = _strong_terms(item.title, item.summary)
    item_seen_at = _parse_time(item.published_at or item.detected_at)

    for event in events:
        if not _within_cooldown(item_seen_at, _parse_time(event.last_seen_at), cooldown_hours):
            continue
        event_title = _normalize_title(event.canonical_title)
        if _conflicting_versions(item.title, event.canonical_title):
            continue
        if _title_similarity(item_title, event_title) >= 0.78:
            return event.event_key
        event_terms = _strong_terms(event.canonical_title, "")
        if item.vendor == event.vendor and item_terms.intersection(event_terms):
            return event.event_key
    return None


def _new_event_key(item: StoredItem) -> str:
    seed = "|".join((item.vendor, canonicalize_url(item.url), _normalize_title(item.title), item.fingerprint))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"evt-{digest}"


def _github_release_key(url: str) -> str | None:
    match = re.search(r"github\.com/([^/]+/[^/]+)/releases/tag/([^/?#]+)", url)
    if not match:
        return None
    return f"{match.group(1).lower()}:{match.group(2).lower()}"


def _trace_string(item: StoredItem, key: str) -> str:
    value = item.trace.get(key)
    return value.strip() if isinstance(value, str) else ""


def _normalize_title(title: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())


def _title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _strong_terms(title: str, summary: str) -> set[str]:
    text = f"{title}\n{summary}".lower()
    return {
        term
        for rule in KEYWORD_RULES
        for term in rule.terms
        if term in text
    }


def _conflicting_versions(left: str, right: str) -> bool:
    left_versions = set(re.findall(r"\b\d+\.\d+(?:\.\d+)?\b", left))
    right_versions = set(re.findall(r"\b\d+\.\d+(?:\.\d+)?\b", right))
    return bool(left_versions and right_versions and left_versions.isdisjoint(right_versions))


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        normalized = f"{normalized}T00:00:00+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _within_cooldown(left: datetime, right: datetime, cooldown_hours: int) -> bool:
    delta_hours = abs((left - right).total_seconds()) / 3600
    return delta_hours <= cooldown_hours
