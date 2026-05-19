from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path

from .models import RadarItem, SourceConfig, utc_now_iso


@dataclass
class FetchBundle:
    items: list[RadarItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def fetch_all(sources: list[SourceConfig], repo_root: Path, timeout_seconds: float = 10.0) -> FetchBundle:
    bundle = FetchBundle()
    for source in sources:
        if not source.enabled:
            continue
        try:
            bundle.items.extend(fetch_source(source, repo_root, timeout_seconds))
        except Exception as exc:  # keep the radar observable rather than brittle
            bundle.errors.append(f"{source.name}: {exc}")
    return bundle


def fetch_source(
    source: SourceConfig,
    repo_root: Path,
    timeout_seconds: float = 10.0,
) -> list[RadarItem]:
    if source.type == "local_json":
        return _limit_items(_fetch_local_json(source, repo_root), source.limit)
    if source.type == "rss":
        return _limit_items(_fetch_rss(source, timeout_seconds), source.limit)
    if source.type == "github_trending":
        return _limit_items(_fetch_github_trending(source, timeout_seconds), source.limit)
    if source.type == "web_page":
        return [_fetch_web_page(source, timeout_seconds)]
    raise ValueError(f"unsupported source type: {source.type}")


def _fetch_local_json(source: SourceConfig, repo_root: Path) -> list[RadarItem]:
    if not source.path:
        raise ValueError("local_json source requires path")
    data_path = Path(source.path)
    if not data_path.is_absolute():
        data_path = repo_root / data_path
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("local_json source must contain a list of items")
    fetched_time = utc_now_iso()
    return [RadarItem.from_mapping(item, source, fetched_time) for item in raw if isinstance(item, dict)]


def _fetch_rss(source: SourceConfig, timeout_seconds: float) -> list[RadarItem]:
    if not source.url:
        raise ValueError("rss source requires url")
    body = _read_url(source.url, timeout_seconds)
    root = ET.fromstring(body)
    fetched_time = utc_now_iso()

    items: list[RadarItem] = []
    channel_items = root.findall(".//item")
    if channel_items:
        for entry in channel_items:
            title = _xml_text(entry, "title")
            url = _xml_text(entry, "link") or source.url
            summary = _strip_html(_xml_text(entry, "description"))
            published_time = _xml_text(entry, "pubDate") or None
            tags = [_clean_text(child.text or "") for child in entry.findall("category")]
            items.append(
                RadarItem(
                    title=title,
                    url=url,
                    source_name=source.name,
                    source_tier=source.tier,
                    source_type=source.type,
                    fetched_time=fetched_time,
                    published_time=published_time,
                    summary=summary,
                    tags=tags + source.areas,
                    raw_category="rss",
                    coverage_area=source.coverage_area,
                    evidence_notes=["Parsed from RSS item metadata."],
                )
            )
        return [item for item in items if item.title]

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        title = _xml_text(entry, "atom:title", ns)
        link = entry.find("atom:link", ns)
        url = link.attrib.get("href", source.url) if link is not None else source.url
        summary = _strip_html(_xml_text(entry, "atom:summary", ns) or _xml_text(entry, "atom:content", ns))
        published_time = _xml_text(entry, "atom:published", ns) or _xml_text(entry, "atom:updated", ns) or None
        tags = [
            _clean_text(child.attrib.get("term", "") or child.text or "")
            for child in entry.findall("atom:category", ns)
        ]
        items.append(
            RadarItem(
                title=title,
                url=url or source.url,
                source_name=source.name,
                source_tier=source.tier,
                source_type=source.type,
                fetched_time=fetched_time,
                published_time=published_time,
                summary=summary,
                tags=[tag for tag in tags if tag] + list(source.areas),
                raw_category="atom",
                coverage_area=source.coverage_area,
                evidence_notes=["Parsed from Atom feed metadata."],
            )
        )
    return [item for item in items if item.title]


def _fetch_github_trending(source: SourceConfig, timeout_seconds: float) -> list[RadarItem]:
    if not source.url:
        raise ValueError("github_trending source requires url")
    html = _read_url(source.url, timeout_seconds)
    fetched_time = utc_now_iso()
    matches = re.findall(
        r'<h2[^>]*>\s*<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    items: list[RadarItem] = []
    for href, raw_title in matches[:25]:
        title = _clean_text(_strip_html(raw_title)).replace(" / ", "/")
        url = "https://github.com" + href if href.startswith("/") else href
        items.append(
            RadarItem(
                title=title,
                url=url,
                source_name=source.name,
                source_tier=source.tier,
                source_type=source.type,
                fetched_time=fetched_time,
                summary="Repository appeared on GitHub Trending.",
                tags=list(source.areas) + ["github", "open source"],
                raw_category="github_trending",
                coverage_area=source.coverage_area,
                evidence_notes=["Parsed from GitHub Trending HTML."],
            )
        )
    if not items:
        raise ValueError("no trending repositories found")
    return items


def _fetch_web_page(source: SourceConfig, timeout_seconds: float) -> RadarItem:
    if not source.url:
        raise ValueError("web_page source requires url")
    html = _read_url(source.url, timeout_seconds)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    title = _clean_text(_strip_html(title_match.group(1))) if title_match else source.name
    summary = _clean_text(unescape(desc_match.group(1))) if desc_match else ""
    return RadarItem(
        title=title,
        url=source.url,
        source_name=source.name,
        source_tier=source.tier,
        source_type=source.type,
        fetched_time=utc_now_iso(),
        summary=summary,
        tags=list(source.areas),
        raw_category="source_page",
        coverage_area=source.coverage_area,
        evidence_notes=["Fetched source page title and description."],
    )


def _read_url(url: str, timeout_seconds: float) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-info-radar/0.1 (+https://example.com/ai-info-radar)",
            "Accept": "text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        raise ValueError(f"fetch failed for {url}: {exc}") from exc


def _xml_text(node: ET.Element, name: str, ns: dict[str, str] | None = None) -> str:
    child = node.find(name, ns or {})
    return _clean_text(child.text or "") if child is not None else ""


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", unescape(value or ""))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _limit_items(items: list[RadarItem], limit: int | None) -> list[RadarItem]:
    return items[:limit] if limit else items
