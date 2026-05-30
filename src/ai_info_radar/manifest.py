from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Source


REQUIRED_FIELDS = {
    "id",
    "name",
    "vendor",
    "source_type",
    "authority_level",
    "url",
    "priority",
    "parsing_strategy",
    "content_type",
}

SUPPORTED_AUTHORITY_LEVELS = {"official", "official_github", "status", "aggregator", "media", "social"}
SUPPORTED_SOURCE_TYPES = {"web_page", "rss", "atom", "github_release", "status_api"}
SUPPORTED_PARSING_STRATEGIES = {"anthropic_engineering_index", "claude_code_changelog"}


class ManifestError(ValueError):
    pass


def load_sources(path: str | Path) -> list[Source]:
    manifest_path = Path(path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = raw.get("sources")
    if not isinstance(entries, list):
        raise ManifestError("Manifest must contain a 'sources' list.")

    sources = [_source_from_mapping(entry, index) for index, entry in enumerate(entries)]
    ids = [source.id for source in sources]
    duplicate_ids = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    if duplicate_ids:
        raise ManifestError(f"Duplicate source ids: {', '.join(duplicate_ids)}")
    return [source for source in sources if source.enabled]


def _source_from_mapping(entry: Any, index: int) -> Source:
    if not isinstance(entry, dict):
        raise ManifestError(f"Source at index {index} must be an object.")

    missing = sorted(REQUIRED_FIELDS - entry.keys())
    if missing:
        raise ManifestError(f"Source at index {index} is missing fields: {', '.join(missing)}")

    source_id = _clean_string(entry["id"], "id", index)
    name = _clean_string(entry["name"], "name", index)
    vendor = _clean_string(entry["vendor"], "vendor", index)
    source_type = _clean_string(entry["source_type"], "source_type", index)
    authority_level = _clean_string(entry["authority_level"], "authority_level", index)
    url = _clean_string(entry["url"], "url", index)
    parsing_strategy = _clean_string(entry["parsing_strategy"], "parsing_strategy", index)
    content_type = _clean_string(entry["content_type"], "content_type", index)

    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ManifestError(f"Unsupported source_type for {source_id}: {source_type}")
    if authority_level not in SUPPORTED_AUTHORITY_LEVELS:
        raise ManifestError(f"Unsupported authority_level for {source_id}: {authority_level}")
    if parsing_strategy not in SUPPORTED_PARSING_STRATEGIES:
        raise ManifestError(f"Unsupported parsing_strategy for {source_id}: {parsing_strategy}")

    try:
        priority = int(entry["priority"])
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"Source {source_id} priority must be an integer.") from exc

    return Source(
        id=source_id,
        name=name,
        vendor=vendor,
        source_type=source_type,
        authority_level=authority_level,
        url=url,
        priority=priority,
        parsing_strategy=parsing_strategy,
        content_type=content_type,
        fixture_path=_optional_string(entry.get("fixture_path")),
        enabled=bool(entry.get("enabled", True)),
    )


def _clean_string(value: Any, field: str, index: int) -> str:
    cleaned = str(value).strip() if value is not None else ""
    if not cleaned:
        raise ManifestError(f"Source at index {index} field '{field}' cannot be empty.")
    return cleaned


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
