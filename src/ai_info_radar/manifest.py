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
    "enabled",
}

SUPPORTED_AUTHORITY_LEVELS = {"official", "official_github", "status", "aggregator", "media", "social"}
SUPPORTED_SOURCE_TYPES = {"web_page", "rss", "atom", "github_release", "status_api"}
SUPPORTED_PARSING_STRATEGIES = {
    "agents_radar_digest",
    "anthropic_engineering_index",
    "claude_code_changelog",
    "official_model_pricing",
    "placeholder",
    "rss_feed",
    "statuspage_incidents",
}


class ManifestError(ValueError):
    pass


def load_sources(path: str | Path, *, include_disabled: bool = False) -> list[Source]:
    manifest_path = Path(path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = raw.get("sources")
    if not isinstance(entries, list):
        raise ManifestError("源清单必须包含 'sources' 列表。")

    sources = [_source_from_mapping(entry, index) for index, entry in enumerate(entries)]
    ids = [source.id for source in sources]
    duplicate_ids = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    if duplicate_ids:
        raise ManifestError(f"重复的来源 id：{', '.join(duplicate_ids)}")
    if include_disabled:
        return sources
    return [source for source in sources if source.enabled]


def _source_from_mapping(entry: Any, index: int) -> Source:
    if not isinstance(entry, dict):
        raise ManifestError(f"索引 {index} 处的来源必须是对象。")

    missing = sorted(REQUIRED_FIELDS - entry.keys())
    if missing:
        raise ManifestError(f"索引 {index} 处的来源缺少字段：{', '.join(missing)}")

    source_id = _clean_string(entry["id"], "id", index)
    name = _clean_string(entry["name"], "name", index)
    vendor = _clean_string(entry["vendor"], "vendor", index)
    source_type = _clean_string(entry["source_type"], "source_type", index)
    authority_level = _clean_string(entry["authority_level"], "authority_level", index)
    url = _clean_string(entry["url"], "url", index)
    parsing_strategy = _clean_string(entry["parsing_strategy"], "parsing_strategy", index)
    content_type = _clean_string(entry["content_type"], "content_type", index)

    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ManifestError(f"{source_id} 的 source_type 不受支持：{source_type}")
    if authority_level not in SUPPORTED_AUTHORITY_LEVELS:
        raise ManifestError(f"{source_id} 的 authority_level 不受支持：{authority_level}")
    if parsing_strategy not in SUPPORTED_PARSING_STRATEGIES:
        raise ManifestError(f"{source_id} 的 parsing_strategy 不受支持：{parsing_strategy}")

    try:
        priority = int(entry["priority"])
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"来源 {source_id} 的 priority 必须是整数。") from exc
    if not isinstance(entry["enabled"], bool):
        raise ManifestError(f"来源 {source_id} 的 enabled 必须是布尔值。")

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
        enabled=entry["enabled"],
    )


def _clean_string(value: Any, field: str, index: int) -> str:
    cleaned = str(value).strip() if value is not None else ""
    if not cleaned:
        raise ManifestError(f"索引 {index} 处来源的字段 '{field}' 不能为空。")
    return cleaned


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
