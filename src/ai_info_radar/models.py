from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    vendor: str
    source_type: str
    authority_level: str
    url: str
    priority: int
    parsing_strategy: str
    content_type: str
    fixture_path: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class FetchedSource:
    source: Source
    body: str
    fetched_at: str
    final_url: str


@dataclass(frozen=True)
class NormalizedItem:
    source_id: str
    source_name: str
    vendor: str
    authority_level: str
    content_type: str
    title: str
    url: str
    detected_at: str
    published_at: str | None
    summary: str
    fingerprint: str
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredItem:
    id: int
    source_id: str
    source_name: str
    vendor: str
    authority_level: str
    content_type: str
    title: str
    url: str
    detected_at: str
    published_at: str | None
    summary: str
    fingerprint: str
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertDecision:
    alert_key: str
    should_alert: bool
    severity: str
    score: int
    reasons: tuple[str, ...]
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class AlertMessage:
    short_id: str
    title: str
    source: str
    authority: str
    why_it_matters: str
    original_link: str
    supporting_sources: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class AlertDeliveryResult:
    ok: bool
    status_code: int | None = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourcePollResult:
    source_id: str
    ok: bool
    inserted: int = 0
    existing: int = 0
    message: str = ""


@dataclass(frozen=True)
class PollResult:
    results: list[SourcePollResult]

    @property
    def inserted(self) -> int:
        return sum(result.inserted for result in self.results)

    @property
    def existing(self) -> int:
        return sum(result.existing for result in self.results)

    @property
    def failures(self) -> int:
        return sum(1 for result in self.results if not result.ok)
