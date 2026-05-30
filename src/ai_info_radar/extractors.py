from __future__ import annotations

import re
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
    raise ExtractionError(f"Unsupported parsing strategy: {strategy}")


def extract_anthropic_engineering(fetched: FetchedSource) -> list[NormalizedItem]:
    parser = _AnthropicEngineeringParser(fetched.final_url)
    parser.feed(fetched.body)
    cards = parser.cards
    if not cards:
        raise ExtractionError(f"No Anthropic Engineering items found for {fetched.source.id}.")

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
        raise ExtractionError(f"Anthropic Engineering cards were incomplete for {fetched.source.id}.")
    return items


def extract_claude_code_changelog(fetched: FetchedSource) -> list[NormalizedItem]:
    parser = _ClaudeCodeChangelogParser(fetched.final_url)
    parser.feed(fetched.body)
    entries = parser.entries
    if not entries:
        raise ExtractionError(f"No Claude Code changelog entries found for {fetched.source.id}.")

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
        raise ExtractionError(f"Claude Code changelog entries were incomplete for {fetched.source.id}.")
    return items


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


class _ClaudeCodeChangelogParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.entries: list[_ChangelogEntry] = []
        self._entry: _ChangelogEntry | None = None
        self._entry_depth = 0
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

        if self._entry is None and self._is_entry_container(tag, attr):
            self._entry = _ChangelogEntry(fragment=attr.get("id", "").strip())
            self._entry_depth = 1
            return

        if self._entry is None:
            return

        self._entry_depth += 1
        if self._capture:
            return

        if tag in {"h1", "h2", "h3", "h4"} and not self._entry.title:
            self._begin_capture("title", tag)
        elif tag == "time" and not self._entry.published_at:
            datetime_value = attr.get("datetime", "").strip()
            if datetime_value:
                self._entry.published_at = datetime_value
            else:
                self._begin_capture("published_at", tag)
        elif tag in {"p", "li"}:
            self._begin_capture("note", tag)

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            if tag in {"script", "style", "footer", "nav", "aside"}:
                self._ignored_depth -= 1
            return

        if self._entry is None:
            return

        if self._capture and tag == self._capture_end_tag:
            captured = _normalize_text("".join(self._buffer))
            if captured:
                if self._capture == "title":
                    self._entry.title = captured
                elif self._capture == "published_at":
                    self._entry.published_at = captured
                elif self._capture == "note":
                    self._entry.summary_parts.append(captured)
            self._capture = None
            self._capture_end_tag = None
            self._buffer = []

        self._entry_depth -= 1
        if self._entry_depth == 0:
            self.entries.append(self._entry)
            self._entry = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not self._capture:
            return
        self._buffer.append(data)

    def _begin_capture(self, field: str, end_tag: str) -> None:
        self._capture = field
        self._capture_end_tag = end_tag
        self._buffer = []

    def _is_entry_container(self, tag: str, attr: dict[str, str]) -> bool:
        if tag not in {"article", "section", "div"}:
            return False
        classes = set(attr.get("class", "").split())
        return (
            "data-changelog-entry" in attr
            or "changelog-entry" in classes
            or attr.get("data-testid") == "changelog-entry"
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


def _normalize_text(value: str) -> str:
    return " ".join(value.split())
