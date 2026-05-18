from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(*parts: str) -> str:
    raw = "\n".join(part.strip().lower() for part in parts if part)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SourceConfig:
    name: str
    tier: str = "lead"
    type: str = "web_page"
    url: str | None = None
    path: str | None = None
    areas: list[str] = field(default_factory=list)
    note: str = ""
    enabled: bool = True
    limit: int | None = None


@dataclass
class RadarItem:
    title: str
    url: str
    source_name: str
    source_tier: str
    source_type: str
    fetched_time: str
    published_time: str | None = None
    summary: str = ""
    claims: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_category: str = ""
    related_focus_topics: list[str] = field(default_factory=list)
    evidence_notes: list[str] = field(default_factory=list)
    world_value: float = 0.0
    learning_value: float = 0.0
    practice_value: float = 0.0
    current_focus_fit: float = 0.0
    final_score: float = 0.0
    confidence: str = "low"
    verification_status: str = "unverified"
    labels: list[str] = field(default_factory=list)
    related_items: list["RadarItem"] = field(default_factory=list)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id(self.url, self.title)

    @property
    def text_for_matching(self) -> str:
        parts = [
            self.title,
            self.summary,
            self.raw_category,
            " ".join(self.claims),
            " ".join(self.tags),
            " ".join(self.related_focus_topics),
        ]
        return " ".join(part for part in parts if part).lower().replace("_", " ")

    @classmethod
    def from_mapping(
        cls,
        data: dict[str, Any],
        source: SourceConfig,
        fetched_time: str | None = None,
    ) -> "RadarItem":
        now = fetched_time or utc_now_iso()
        return cls(
            title=str(data.get("title", "")).strip(),
            url=str(data.get("url") or source.url or "").strip(),
            source_name=str(data.get("source_name") or source.name).strip(),
            source_tier=str(data.get("source_tier") or source.tier).strip(),
            source_type=str(data.get("source_type") or source.type).strip(),
            fetched_time=str(data.get("fetched_time") or now).strip(),
            published_time=(
                str(data["published_time"]).strip()
                if data.get("published_time") is not None
                else None
            ),
            summary=str(data.get("summary", "")).strip(),
            claims=[str(item).strip() for item in data.get("claims", []) if str(item).strip()],
            tags=[str(item).strip() for item in data.get("tags", []) if str(item).strip()],
            raw_category=str(data.get("raw_category", "")).strip(),
            related_focus_topics=[
                str(item).strip()
                for item in data.get("related_focus_topics", [])
                if str(item).strip()
            ],
            evidence_notes=[
                str(item).strip() for item in data.get("evidence_notes", []) if str(item).strip()
            ],
        )


@dataclass(frozen=True)
class FocusConfig:
    name: str = "General AI"
    description: str = ""
    weight: float = 1.0
    keywords: list[str] = field(default_factory=list)
    secondary_interests: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoringConfig:
    weights: dict[str, float]
    thresholds: dict[str, float]


@dataclass
class RadarRun:
    items: list[RadarItem]
    fetch_errors: list[str]
    generated_at: str
