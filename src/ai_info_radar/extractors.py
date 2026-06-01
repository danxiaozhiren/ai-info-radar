from __future__ import annotations

import email.utils
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin

from .fingerprint import content_fingerprint
from .models import FetchedSource, NormalizedItem


class ExtractionError(RuntimeError):
    pass


def extract_items(fetched: FetchedSource) -> list[NormalizedItem]:
    strategy = fetched.source.parsing_strategy
    if strategy == "anthropic_engineering_index":
        return extract_anthropic_engineering(fetched)
    if strategy == "claude_code_changelog":
        return extract_claude_code_changelog(fetched)
    if strategy == "agents_radar_digest":
        return extract_agents_radar_digest(fetched)
    if strategy == "statuspage_incidents":
        return extract_statuspage_incidents(fetched)
    if strategy == "official_model_pricing":
        return extract_official_model_pricing(fetched)
    if strategy == "rss_feed":
        return extract_rss_feed(fetched)
    raise ExtractionError(f"不支持的解析策略：{strategy}")


def extract_anthropic_engineering(fetched: FetchedSource) -> list[NormalizedItem]:
    parser = _AnthropicEngineeringParser(fetched.final_url)
    parser.feed(fetched.body)
    cards = parser.cards
    if not cards:
        raise ExtractionError(f"{fetched.source.id} 未找到 Anthropic Engineering 条目。")

    items: list[NormalizedItem] = []
    for position, card in enumerate(cards, start=1):
        title = card.title.strip()
        url = card.url.strip()
        if not title or not url:
            continue
        summary = card.summary.strip()
        published_at = card.published_at.strip() or None
        fingerprint = content_fingerprint(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            vendor=fetched.source.vendor,
            content_type=fetched.source.content_type,
        )
        items.append(
            NormalizedItem(
                source_id=fetched.source.id,
                source_name=fetched.source.name,
                vendor=fetched.source.vendor,
                authority_level=fetched.source.authority_level,
                content_type=fetched.source.content_type,
                title=title,
                url=url,
                detected_at=fetched.fetched_at,
                published_at=published_at,
                summary=summary,
                fingerprint=fingerprint,
                trace={
                    "parser": fetched.source.parsing_strategy,
                    "position": position,
                    "fetched_url": fetched.final_url,
                },
            )
        )
    if not items:
        raise ExtractionError(f"{fetched.source.id} 的 Anthropic Engineering 卡片信息不完整。")
    return items


def extract_claude_code_changelog(fetched: FetchedSource) -> list[NormalizedItem]:
    entries = _parse_markdown_changelog(fetched.body)
    if not entries:
        raise ExtractionError(f"{fetched.source.id} 未找到 Claude Code 更新日志条目。")

    items: list[NormalizedItem] = []
    for position, entry in enumerate(entries, start=1):
        raw_title = entry.title.strip()
        summary = " ".join(entry.summary_parts).strip()
        if not raw_title or not summary:
            continue
        title = _claude_code_title(raw_title)
        fragment = entry.fragment or _slugify(title)
        url = _with_fragment(fetched.final_url, fragment)
        published_at = entry.published_at.strip() or None
        fingerprint = content_fingerprint(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            vendor=fetched.source.vendor,
            content_type=fetched.source.content_type,
        )
        items.append(
            NormalizedItem(
                source_id=fetched.source.id,
                source_name=fetched.source.name,
                vendor=fetched.source.vendor,
                authority_level=fetched.source.authority_level,
                content_type=fetched.source.content_type,
                title=title,
                url=url,
                detected_at=fetched.fetched_at,
                published_at=published_at,
                summary=summary,
                fingerprint=fingerprint,
                trace={
                    "parser": fetched.source.parsing_strategy,
                    "position": position,
                    "fetched_url": fetched.final_url,
                    "entry_id": fragment,
                    "raw_title": raw_title,
                },
            )
        )
    if not items:
        raise ExtractionError(f"{fetched.source.id} 的 Claude Code 更新日志条目信息不完整。")
    return items


def _parse_markdown_changelog(body: str) -> list[_ChangelogEntry]:
    entries: list[_ChangelogEntry] = []
    current: _ChangelogEntry | None = None

    for line in body.splitlines():
        heading_match = re.match(r"^##\s+(.+)$", line)
        if heading_match:
            if current is not None:
                entries.append(current)
            version = heading_match.group(1).strip()
            current = _ChangelogEntry(
                fragment=_slugify(version),
                title=version,
            )
            continue

        if current is None:
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        if bullet_match:
            current.summary_parts.append(bullet_match.group(1).strip())
        elif line.strip() and current.summary_parts:
            current.summary_parts[-1] += " " + line.strip()

    if current is not None:
        entries.append(current)

    return entries


def extract_agents_radar_digest(fetched: FetchedSource) -> list[NormalizedItem]:
    parser = _AgentsRadarDigestParser(fetched.final_url)
    parser.feed(fetched.body)
    cards = parser.cards
    if not cards:
        raise ExtractionError(f"{fetched.source.id} 未找到 agents-radar 候选条目。")

    items: list[NormalizedItem] = []
    for position, card in enumerate(cards, start=1):
        title = card.title.strip()
        url = card.url.strip()
        if not title or not url:
            continue
        summary = card.summary.strip()
        published_at = card.published_at.strip() or None
        fingerprint = content_fingerprint(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            vendor=fetched.source.vendor,
            content_type=fetched.source.content_type,
        )
        trace = {
            "parser": fetched.source.parsing_strategy,
            "position": position,
            "fetched_url": fetched.final_url,
        }
        if card.target_url:
            trace["target_url"] = card.target_url
        if card.target_source:
            trace["target_source"] = card.target_source
        items.append(
            NormalizedItem(
                source_id=fetched.source.id,
                source_name=fetched.source.name,
                vendor=fetched.source.vendor,
                authority_level=fetched.source.authority_level,
                content_type=fetched.source.content_type,
                title=title,
                url=url,
                detected_at=fetched.fetched_at,
                published_at=published_at,
                summary=summary,
                fingerprint=fingerprint,
                trace=trace,
            )
        )
    if not items:
        raise ExtractionError(f"{fetched.source.id} 的 agents-radar 候选卡片信息不完整。")
    return items


def extract_statuspage_incidents(fetched: FetchedSource) -> list[NormalizedItem]:
    try:
        payload = json.loads(fetched.body)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"{fetched.source.id} 的 Statuspage 响应不是合法 JSON。") from exc

    incidents = payload.get("incidents")
    if not isinstance(incidents, list):
        raise ExtractionError(f"{fetched.source.id} 的 Statuspage 响应不包含 incidents 列表。")

    items: list[NormalizedItem] = []
    for position, incident in enumerate(incidents, start=1):
        if not isinstance(incident, dict):
            continue
        status_id = _json_string(incident, "id")
        name = _json_string(incident, "name")
        status = _json_string(incident, "status")
        impact = _json_string(incident, "impact")
        url = _json_string(incident, "shortlink") or _with_fragment(fetched.final_url, status_id)
        published_at = _json_string(incident, "created_at") or None
        latest_update = _latest_status_update(incident)
        if not status_id or not name or not url:
            continue

        title = f"Status {status or 'incident'}: {name}"
        summary = _status_summary(
            status=status,
            impact=impact,
            latest_update=latest_update,
            affected_components=_affected_components(incident),
        )
        fingerprint = content_fingerprint(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            vendor=fetched.source.vendor,
            content_type=fetched.source.content_type,
        )
        items.append(
            NormalizedItem(
                source_id=fetched.source.id,
                source_name=fetched.source.name,
                vendor=fetched.source.vendor,
                authority_level=fetched.source.authority_level,
                content_type=fetched.source.content_type,
                title=title,
                url=url,
                detected_at=fetched.fetched_at,
                published_at=published_at,
                summary=summary,
                fingerprint=fingerprint,
                trace={
                    "parser": fetched.source.parsing_strategy,
                    "position": position,
                    "fetched_url": fetched.final_url,
                    "source_item_id": status_id,
                    "statuspage_status": status,
                    "impact": impact,
                    "updated_at": _json_string(incident, "updated_at"),
                    "resolved_at": _json_string(incident, "resolved_at"),
                    "canonical_url": url,
                },
            )
        )
    return items


def extract_official_model_pricing(fetched: FetchedSource) -> list[NormalizedItem]:
    parser = _OfficialModelPricingParser(fetched.final_url)
    parser.feed(fetched.body)
    records = parser.records
    if not records:
        raise ExtractionError(f"{fetched.source.id} 未找到模型价格记录。")

    items: list[NormalizedItem] = []
    for position, record in enumerate(records, start=1):
        model = record.model.strip()
        if not model:
            continue
        title = f"Model pricing: {model}"
        url = _with_fragment(fetched.final_url, record.fragment or _slugify(model))
        published_at = record.effective_date.strip() or None
        summary = _model_pricing_summary(record)
        fingerprint = content_fingerprint(
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            vendor=fetched.source.vendor,
            content_type=fetched.source.content_type,
        )
        trace = {
            "parser": fetched.source.parsing_strategy,
            "position": position,
            "fetched_url": fetched.final_url,
            "source_item_id": model,
            "canonical_url": url,
            "model": model,
            "input_price_per_million": record.input_price,
            "output_price_per_million": record.output_price,
            "context_window": record.context_window,
            "capabilities": tuple(record.capabilities),
            "rate_limit": record.rate_limit,
            "deprecation": record.deprecation,
            "migration": record.migration,
        }
        items.append(
            NormalizedItem(
                source_id=fetched.source.id,
                source_name=fetched.source.name,
                vendor=fetched.source.vendor,
                authority_level=fetched.source.authority_level,
                content_type=fetched.source.content_type,
                title=title,
                url=url,
                detected_at=fetched.fetched_at,
                published_at=published_at,
                summary=summary,
                fingerprint=fingerprint,
                trace=trace,
            )
        )
    if not items:
        raise ExtractionError(f"{fetched.source.id} 的模型价格记录信息不完整。")
    return items


_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def extract_rss_feed(fetched: FetchedSource) -> list[NormalizedItem]:
    try:
        root = ET.fromstring(fetched.body)
    except ET.ParseError as exc:
        raise ExtractionError(f"{fetched.source.id} 的 RSS/Atom 响应不是合法 XML。") from exc

    feed_format, entries = _detect_feed_entries(root)
    if not entries:
        raise ExtractionError(f"{fetched.source.id} 未找到 RSS/Atom 条目。")

    items: list[NormalizedItem] = []
    for position, entry in enumerate(entries, start=1):
        title = _rss_text(entry, "title", feed_format)
        link = _rss_link(entry, feed_format)
        published_at = _rss_date(entry, feed_format)
        summary = _rss_description(entry, feed_format)
        if not title or not link:
            continue
        fingerprint = content_fingerprint(
            title=title,
            url=link,
            published_at=published_at,
            summary=summary,
            vendor=fetched.source.vendor,
            content_type=fetched.source.content_type,
        )
        items.append(
            NormalizedItem(
                source_id=fetched.source.id,
                source_name=fetched.source.name,
                vendor=fetched.source.vendor,
                authority_level=fetched.source.authority_level,
                content_type=fetched.source.content_type,
                title=title,
                url=link,
                detected_at=fetched.fetched_at,
                published_at=published_at,
                summary=summary,
                fingerprint=fingerprint,
                trace={
                    "parser": "rss_feed",
                    "feed_format": feed_format,
                    "position": position,
                    "fetched_url": fetched.final_url,
                },
            )
        )
    if not items:
        raise ExtractionError(f"{fetched.source.id} 的 RSS/Atom 条目信息不完整。")
    return items


def _detect_feed_entries(root: ET.Element) -> tuple[str, list[ET.Element]]:
    if root.tag == "rss" or root.tag.endswith("}rss"):
        return "rss", root.findall(".//item")
    if root.tag == "{http://www.w3.org/2005/Atom}feed" or root.tag == "feed":
        return "atom", root.findall("atom:entry", _ATOM_NS) or root.findall("entry")
    if root.tag == "channel":
        return "rss", root.findall("item")
    rss_items = root.findall(".//item")
    if rss_items:
        return "rss", rss_items
    atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    if atom_entries:
        return "atom", atom_entries
    return "unknown", []


def _find_atom(entry: ET.Element, tag: str, feed_format: str) -> ET.Element | None:
    if feed_format == "atom":
        elem = entry.find(f"atom:{tag}", _ATOM_NS)
        if elem is not None:
            return elem
        return entry.find(tag)
    return entry.find(tag)


def _rss_text(entry: ET.Element, tag: str, feed_format: str) -> str:
    elem = _find_atom(entry, tag, feed_format)
    return _strip_html(elem.text or "") if elem is not None else ""


def _rss_link(entry: ET.Element, feed_format: str) -> str:
    if feed_format == "atom":
        link_elem = _find_atom(entry, "link", feed_format)
        if link_elem is not None:
            href = link_elem.get("href", "").strip()
            if href:
                return href
        link_elem = entry.find("atom:link[@rel='alternate']", _ATOM_NS)
        if link_elem is not None:
            return link_elem.get("href", "").strip()
    else:
        link_elem = entry.find("link")
        if link_elem is not None:
            text = (link_elem.text or "").strip()
            if text:
                return text
    return ""


def _rss_date(entry: ET.Element, feed_format: str) -> str | None:
    tags = (
        ["published", "updated"]
        if feed_format == "atom"
        else ["pubDate", "published", "updated"]
    )
    for tag in tags:
        elem = _find_atom(entry, tag, feed_format)
        if elem is not None and elem.text and elem.text.strip():
            return _normalize_date(elem.text.strip())
    return None


def _rss_description(entry: ET.Element, feed_format: str) -> str:
    if feed_format == "atom":
        for tag in ("summary", "content"):
            elem = _find_atom(entry, tag, feed_format)
            if elem is not None and elem.text:
                return _strip_html(elem.text)
    else:
        for tag in ("description", "content:encoded"):
            elem = entry.find(tag)
            if elem is not None and elem.text:
                return _strip_html(elem.text)
    return ""


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    return _normalize_text(_HTML_TAG_RE.sub("", value))


_DATE_PATTERNS: list[tuple[str, str]] = [
    (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "iso"),
    (r"^\d{4}-\d{2}-\d{2}", "iso_date"),
]


def _normalize_date(raw: str) -> str:
    for pattern, kind in _DATE_PATTERNS:
        if re.match(pattern, raw):
            return raw
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
        return parsed.isoformat()
    except (ValueError, TypeError):
        return raw


@dataclass
class _ArticleCard:
    title: str = ""
    url: str = ""
    published_at: str = ""
    summary: str = ""


@dataclass
class _ChangelogEntry:
    fragment: str = ""
    title: str = ""
    published_at: str = ""
    summary_parts: list[str] = field(default_factory=list)


@dataclass
class _AggregatorCard:
    title: str = ""
    url: str = ""
    target_url: str = ""
    target_source: str = ""
    published_at: str = ""
    summary: str = ""


@dataclass
class _ModelPricingRecord:
    fragment: str = ""
    model: str = ""
    input_price: str = ""
    output_price: str = ""
    context_window: str = ""
    rate_limit: str = ""
    deprecation: str = ""
    migration: str = ""
    effective_date: str = ""
    capabilities: list[str] = field(default_factory=list)


class _AnthropicEngineeringParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[_ArticleCard] = []
        self._card: _ArticleCard | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag in {"script", "style", "footer", "nav", "aside"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return

        if tag == "article":
            self._card = _ArticleCard()
            return

        if self._card is None:
            return

        if tag == "a" and not self._card.url:
            href = attr.get("href", "").strip()
            if href:
                self._card.url = urljoin(self.base_url, href)
        elif tag in {"h1", "h2", "h3"} and not self._card.title:
            self._begin_capture("title")
        elif tag == "time" and not self._card.published_at:
            datetime_value = attr.get("datetime", "").strip()
            if datetime_value:
                self._card.published_at = datetime_value
            else:
                self._begin_capture("published_at")
        elif tag == "p" and not self._card.summary:
            self._begin_capture("summary")

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            if tag in {"script", "style", "footer", "nav", "aside"}:
                self._ignored_depth -= 1
            return

        if self._capture and tag in {"h1", "h2", "h3", "time", "p"}:
            captured = " ".join("".join(self._buffer).split())
            if self._card is not None and captured:
                setattr(self._card, self._capture, captured)
            self._capture = None
            self._buffer = []
            return

        if tag == "article" and self._card is not None:
            self.cards.append(self._card)
            self._card = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not self._capture:
            return
        self._buffer.append(data)

    def _begin_capture(self, field: str) -> None:
        self._capture = field
        self._buffer = []


class _AgentsRadarDigestParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.cards: list[_AggregatorCard] = []
        self._card: _AggregatorCard | None = None
        self._card_depth = 0
        self._capture: str | None = None
        self._capture_end_tag: str | None = None
        self._buffer: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag in {"script", "style", "footer", "nav", "aside"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return

        if self._card is None and self._is_card_container(tag, attr):
            target_url = attr.get("data-target-url", "").strip()
            self._card = _AggregatorCard(
                target_url=urljoin(self.base_url, target_url) if target_url else "",
                target_source=attr.get("data-target-source", "").strip(),
            )
            self._card_depth = 1
            return

        if self._card is None:
            return

        self._card_depth += 1
        if tag == "a":
            href = attr.get("href", "").strip()
            role = attr.get("data-link-role", "").strip()
            if href and role == "aggregator" and not self._card.url:
                self._card.url = urljoin(self.base_url, href)
            elif href and role == "target" and not self._card.target_url:
                self._card.target_url = urljoin(self.base_url, href)
            elif href and not self._card.url:
                self._card.url = urljoin(self.base_url, href)

        if self._capture:
            return

        if tag in {"h1", "h2", "h3", "h4"} and not self._card.title:
            self._begin_capture("title", tag)
        elif tag == "time" and not self._card.published_at:
            datetime_value = attr.get("datetime", "").strip()
            if datetime_value:
                self._card.published_at = datetime_value
            else:
                self._begin_capture("published_at", tag)
        elif tag == "p" and not self._card.summary:
            self._begin_capture("summary", tag)

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            if tag in {"script", "style", "footer", "nav", "aside"}:
                self._ignored_depth -= 1
            return

        if self._card is None:
            return

        if self._capture and tag == self._capture_end_tag:
            captured = _normalize_text("".join(self._buffer))
            if captured:
                setattr(self._card, self._capture, captured)
            self._capture = None
            self._capture_end_tag = None
            self._buffer = []

        self._card_depth -= 1
        if self._card_depth == 0:
            self.cards.append(self._card)
            self._card = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not self._capture:
            return
        self._buffer.append(data)

    def _begin_capture(self, field: str, end_tag: str) -> None:
        self._capture = field
        self._capture_end_tag = end_tag
        self._buffer = []

    def _is_card_container(self, tag: str, attr: dict[str, str]) -> bool:
        if tag not in {"article", "section", "div"}:
            return False
        classes = set(attr.get("class", "").split())
        return (
            "data-aggregator-item" in attr
            or "agents-radar-item" in classes
            or attr.get("data-testid") == "agents-radar-item"
        )


class _OfficialModelPricingParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.records: list[_ModelPricingRecord] = []
        self._in_table = 0
        self._in_row = False
        self._in_cell = False
        self._cells: list[str] = []
        self._cell_buffer: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "aside"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return

        if tag == "table":
            self._in_table += 1
        elif tag == "tr" and self._in_table > 0:
            self._in_row = True
            self._cells = []
        elif tag in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._cell_buffer = []

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            if tag in {"script", "style", "nav", "aside"}:
                self._ignored_depth -= 1
            return

        if tag in {"td", "th"} and self._in_cell:
            self._in_cell = False
            self._cells.append(_normalize_text("".join(self._cell_buffer)))
        elif tag == "tr" and self._in_row:
            self._in_row = False
            self._maybe_add_row()
        elif tag == "table" and self._in_table > 0:
            self._in_table -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not self._in_cell:
            return
        self._cell_buffer.append(data)

    def _maybe_add_row(self) -> None:
        if len(self._cells) < 7:
            return
        model = self._cells[0].strip()
        if not model or not re.match(r"^[a-z]", model, re.IGNORECASE):
            return
        if model.lower() in {"model", "input", "output", "cached input"}:
            return
        if not re.search(r"\d", model) and " " in model:
            return

        input_price = self._cells[1] if len(self._cells) > 1 else ""
        cached_input = self._cells[2] if len(self._cells) > 2 else ""
        output_price = self._cells[3] if len(self._cells) > 3 else ""

        self.records.append(
            _ModelPricingRecord(
                fragment=_slugify(model),
                model=model,
                input_price=input_price,
                output_price=output_price,
            )
        )


def _claude_code_title(raw_title: str) -> str:
    title = _normalize_text(raw_title)
    if title.lower().startswith("claude code"):
        return title
    return f"Claude Code {title}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entry"


def _with_fragment(url: str, fragment: str) -> str:
    base, _ = urldefrag(url)
    return f"{base}#{fragment}"


def _json_string(mapping: dict[object, object], key: str) -> str:
    value = mapping.get(key)
    return value.strip() if isinstance(value, str) else ""


def _latest_status_update(incident: dict[object, object]) -> dict[object, object]:
    updates = incident.get("incident_updates")
    if not isinstance(updates, list):
        return {}
    for update in updates:
        if isinstance(update, dict):
            return update
    return {}


def _affected_components(incident: dict[object, object]) -> tuple[str, ...]:
    names: list[str] = []
    components = incident.get("components")
    if isinstance(components, list):
        for component in components:
            if not isinstance(component, dict):
                continue
            name = _json_string(component, "name")
            status = _json_string(component, "status")
            if name:
                names.append(f"{name} ({status})" if status else name)
    return tuple(names)


def _status_summary(
    *,
    status: str,
    impact: str,
    latest_update: dict[object, object],
    affected_components: tuple[str, ...],
) -> str:
    parts = []
    if status:
        parts.append(f"Status: {status}.")
    if impact:
        parts.append(f"Impact: {impact}.")
    latest_status = _json_string(latest_update, "status")
    latest_body = _json_string(latest_update, "body")
    if latest_status or latest_body:
        parts.append(f"Latest update: {latest_status} - {latest_body}".strip())
    if affected_components:
        parts.append(f"Affected components: {', '.join(affected_components)}.")
    return " ".join(parts)


def _model_pricing_summary(record: _ModelPricingRecord) -> str:
    parts = [f"Model: {record.model}."]
    if record.input_price:
        parts.append(f"Input price: {record.input_price}.")
    if record.output_price:
        parts.append(f"Output price: {record.output_price}.")
    if record.context_window:
        parts.append(f"Context: {record.context_window}.")
    if record.capabilities:
        parts.append(f"Capabilities: {', '.join(tuple(dict.fromkeys(record.capabilities)))}.")
    if record.rate_limit:
        parts.append(f"Rate limit: {record.rate_limit}.")
    if record.deprecation:
        parts.append(f"Deprecation: {record.deprecation}.")
    if record.migration:
        parts.append(f"Migration: {record.migration}.")
    return " ".join(parts)


def _split_capabilities(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_text(value: str) -> str:
    return " ".join(value.split())
