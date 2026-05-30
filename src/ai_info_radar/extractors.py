from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from .fingerprint import content_fingerprint
from .models import FetchedSource, NormalizedItem


class ExtractionError(RuntimeError):
    pass


def extract_items(fetched: FetchedSource) -> list[NormalizedItem]:
    strategy = fetched.source.parsing_strategy
    if strategy == "anthropic_engineering_index":
        return extract_anthropic_engineering(fetched)
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


@dataclass
class _ArticleCard:
    title: str = ""
    url: str = ""
    published_at: str = ""
    summary: str = ""


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
