from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import FocusConfig, ScoringConfig, SourceConfig


class ConfigError(ValueError):
    pass


def load_config(path: str | Path) -> Any:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ModuleNotFoundError:
        return _parse_yaml_subset(text)


def load_sources(path: str | Path) -> list[SourceConfig]:
    data = load_config(path)
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ConfigError("sources config must contain a list named 'sources'")

    loaded: list[SourceConfig] = []
    for raw in sources:
        if not isinstance(raw, dict):
            raise ConfigError("each source must be a mapping")
        name = str(raw.get("name", "")).strip()
        if not name:
            raise ConfigError("source is missing a name")
        source_type = str(raw.get("type") or _infer_source_type(raw)).strip()
        loaded.append(
            SourceConfig(
                name=name,
                tier=str(raw.get("tier", "lead")).strip(),
                type=source_type,
                url=_optional_str(raw.get("url")),
                path=_optional_str(raw.get("path")),
                areas=[str(item).strip() for item in raw.get("areas", []) if str(item).strip()],
                note=str(raw.get("note", "")).strip(),
                enabled=bool(raw.get("enabled", True)),
                limit=_optional_int(raw.get("limit")),
            )
        )
    return loaded


def load_focus(path: str | Path) -> FocusConfig:
    data = load_config(path)
    raw = data.get("current_focus", {})
    if not isinstance(raw, dict):
        raise ConfigError("focus config must contain a mapping named 'current_focus'")
    return FocusConfig(
        name=str(raw.get("name", "General AI")).strip(),
        description=str(raw.get("description", "")).strip(),
        weight=float(raw.get("weight", 1.0)),
        keywords=[str(item).strip() for item in raw.get("keywords", []) if str(item).strip()],
        secondary_interests=[
            str(item).strip()
            for item in data.get("secondary_interests", [])
            if str(item).strip()
        ],
    )


def load_scoring(path: str | Path) -> ScoringConfig:
    data = load_config(path)
    weights = data.get("weights", {})
    thresholds = data.get("thresholds", {})
    if not isinstance(weights, dict) or not isinstance(thresholds, dict):
        raise ConfigError("scoring config must contain weights and thresholds mappings")
    return ScoringConfig(
        weights={str(key): float(value) for key, value in weights.items()},
        thresholds={str(key): float(value) for key, value in thresholds.items()},
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    number = int(value)
    return number if number > 0 else None


def _infer_source_type(raw: dict[str, Any]) -> str:
    if raw.get("path"):
        return "local_json"
    url = str(raw.get("url", "")).lower()
    if "github.com/trending" in url:
        return "github_trending"
    if url.endswith(".xml") or url.endswith(".atom") or "rss" in url or "feed" in url:
        return "rss"
    return "web_page"


def _parse_yaml_subset(text: str) -> Any:
    lines: list[tuple[int, str]] = []
    for original in text.splitlines():
        if not original.strip() or original.lstrip().startswith("#"):
            continue
        indent = len(original) - len(original.lstrip(" "))
        lines.append((indent, original.strip()))
    if not lines:
        return {}
    value, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ConfigError(f"could not parse YAML subset near: {lines[index][1]}")
    return value


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, content = lines[index]
    if current_indent < indent:
        return {}, index
    if content.startswith("- "):
        return _parse_list(lines, index, current_indent)
    return _parse_mapping(lines, index, current_indent)


def _parse_mapping(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError(f"unexpected indentation near: {content}")
        if content.startswith("- "):
            break
        key, raw_value = _split_key_value(content)
        index += 1
        if raw_value == "":
            if index < len(lines) and lines[index][0] > current_indent:
                child, index = _parse_block(lines, index, lines[index][0])
                result[key] = child
            else:
                result[key] = {}
        else:
            result[key] = _parse_scalar(raw_value)
    return result, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError(f"unexpected indentation near: {content}")
        if not content.startswith("- "):
            break

        item_text = content[2:].strip()
        index += 1
        if not item_text:
            child, index = _parse_block(lines, index, indent + 2)
            result.append(child)
            continue

        if ":" in item_text:
            key, raw_value = _split_key_value(item_text)
            item: dict[str, Any] = {}
            if raw_value == "":
                child, index = _parse_block(lines, index, indent + 2)
                item[key] = child
            else:
                item[key] = _parse_scalar(raw_value)

            if index < len(lines) and lines[index][0] > indent:
                child, index = _parse_block(lines, index, lines[index][0])
                if not isinstance(child, dict):
                    raise ConfigError(f"expected mapping after list item: {item_text}")
                item.update(child)
            result.append(item)
        else:
            result.append(_parse_scalar(item_text))
    return result, index


def _split_key_value(content: str) -> tuple[str, str]:
    if ":" not in content:
        raise ConfigError(f"expected key/value pair near: {content}")
    key, raw_value = content.split(":", 1)
    key = key.strip()
    if not key:
        raise ConfigError(f"empty key near: {content}")
    return key, raw_value.strip()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
