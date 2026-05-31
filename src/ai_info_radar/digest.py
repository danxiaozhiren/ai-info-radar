from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from .events import merge_events
from .models import AlertDeliveryResult, AlertHistoryEntry, SourceHealthEntry, StoredItem
from .notifiers import build_feishu_text_payload, send_feishu_text_webhook
from .store import RadarStore


@dataclass(frozen=True)
class DigestContent:
    report_date: date
    alerted_items: tuple[AlertHistoryEntry, ...]
    worth_reading_items: tuple[StoredItem, ...]
    saved_items: tuple[StoredItem, ...]
    source_failures: tuple[SourceHealthEntry, ...]
    state_counts: dict[str, int]
    total_items: int
    marked_digested: int


@dataclass(frozen=True)
class DigestRunResult:
    status: str
    message: str
    report_path: Path
    sent: bool
    payload: dict[str, object]
    marked_digested: int


DigestSender = Callable[[str, str], AlertDeliveryResult]


def generate_daily_digest(
    *,
    db_path: str | Path,
    reports_dir: str | Path,
    webhook_url: str | None = None,
    report_date: date | None = None,
    sender: DigestSender | None = None,
    timeout_seconds: float = 10.0,
) -> DigestRunResult:
    current_date = report_date or date.today()
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    report_path = reports_path / f"ai-radar-digest-{current_date.isoformat()}.md"

    with RadarStore(db_path) as store:
        content = build_digest_content(store, current_date)
        marked = store.mark_new_items_daily(_included_item_ids(content))
        content = DigestContent(
            report_date=content.report_date,
            alerted_items=content.alerted_items,
            worth_reading_items=content.worth_reading_items,
            saved_items=content.saved_items,
            source_failures=content.source_failures,
            state_counts=store.item_state_counts(),
            total_items=content.total_items,
            marked_digested=marked,
        )

    markdown = render_digest_markdown(content)
    report_path.write_text(markdown, encoding="utf-8")
    text = render_digest_text(content)
    payload = build_feishu_text_payload(text)

    if not webhook_url:
        return DigestRunResult(
            status="prepared",
            message="report written; FEISHU_WEBHOOK_URL not configured",
            report_path=report_path,
            sent=False,
            payload=payload,
            marked_digested=marked,
        )

    effective_sender = sender or (
        lambda url, digest_text: send_feishu_text_webhook(
            url,
            digest_text,
            timeout_seconds=timeout_seconds,
        )
    )
    delivery = effective_sender(webhook_url, text)
    if not delivery.ok:
        return DigestRunResult(
            status="failed",
            message=delivery.message or "Feishu digest delivery failed",
            report_path=report_path,
            sent=False,
            payload=delivery.payload or payload,
            marked_digested=marked,
        )

    return DigestRunResult(
        status="sent",
        message="Feishu digest sent",
        report_path=report_path,
        sent=True,
        payload=delivery.payload or payload,
        marked_digested=marked,
    )


def build_digest_content(store: RadarStore, report_date: date) -> DigestContent:
    merge_events(store)
    items = store.list_items()
    alerts = tuple(
        store.list_alert_history(
            exclude_item_states={"daily", "digested", "ignored", "read", "saved"}
        )
    )
    alerted_item_ids = {alert.item_id for alert in alerts}
    saved_items = tuple(item for item in items if item.state == "saved")
    worth_reading_items = tuple(
        item
        for item in items
        if item.state == "new" and item.id not in alerted_item_ids
    )
    source_failures = tuple(store.list_source_failures())
    return DigestContent(
        report_date=report_date,
        alerted_items=alerts,
        worth_reading_items=worth_reading_items,
        saved_items=saved_items,
        source_failures=source_failures,
        state_counts=store.item_state_counts(),
        total_items=len(items),
        marked_digested=0,
    )


def render_digest_markdown(content: DigestContent) -> str:
    lines = [
        f"# AI Radar Morning Digest - {content.report_date.isoformat()}",
        "",
        "## Already Alerted",
        *_render_alerts(content.alerted_items),
        "",
        "## Worth Reading",
        *_render_items(content.worth_reading_items),
        "",
        "## Saved",
        *_render_items(content.saved_items),
        "",
        "## Source Failures",
        *_render_failures(content.source_failures),
        "",
        "## Filtering Statistics",
        f"- Total stored items: {content.total_items}",
        f"- Already alerted: {len(content.alerted_items)}",
        f"- Worth reading: {len(content.worth_reading_items)}",
        f"- Saved: {len(content.saved_items)}",
        f"- Source failures: {len(content.source_failures)}",
        f"- Marked in daily: {content.marked_digested}",
        f"- State counts: {_format_state_counts(content.state_counts)}",
        "",
    ]
    return "\n".join(lines)


def render_digest_text(content: DigestContent) -> str:
    lines = [
        f"AI Radar Morning Digest - {content.report_date.isoformat()}",
        (
            f"Alerted {len(content.alerted_items)} | "
            f"Worth reading {len(content.worth_reading_items)} | "
            f"Saved {len(content.saved_items)} | "
            f"Failures {len(content.source_failures)}"
        ),
    ]
    if content.alerted_items:
        lines.append("Already alerted:")
        lines.extend(f"- {alert.title} ({alert.source_name}) {alert.url}" for alert in content.alerted_items[:5])
    if content.worth_reading_items:
        lines.append("Worth reading:")
        lines.extend(f"- {item.title} ({item.source_name}) {item.url}" for item in content.worth_reading_items[:8])
    if content.saved_items:
        lines.append("Saved:")
        lines.extend(f"- {item.title} ({item.source_name}) {item.url}" for item in content.saved_items[:5])
    if content.source_failures:
        lines.append("Source failures:")
        lines.extend(f"- {failure.source_id}: {failure.message}" for failure in content.source_failures[:5])
    lines.append(f"Marked in daily: {content.marked_digested}")
    return "\n".join(lines)


def _included_item_ids(content: DigestContent) -> list[int]:
    ids = [alert.item_id for alert in content.alerted_items]
    ids.extend(item.id for item in content.worth_reading_items)
    ids.extend(item.id for item in content.saved_items)
    return list(dict.fromkeys(ids))


def _render_alerts(alerts: tuple[AlertHistoryEntry, ...]) -> list[str]:
    if not alerts:
        return ["- None."]
    rendered = []
    for alert in alerts:
        line = f"- [{alert.title}]({alert.url}) - {alert.source_name}; alerted at {alert.alerted_at}"
        if alert.supporting_sources:
            line += f"; supporting: {', '.join(alert.supporting_sources)}"
        rendered.append(line)
    return rendered


def _render_items(items: tuple[StoredItem, ...]) -> list[str]:
    if not items:
        return ["- None."]
    rendered = []
    for item in items:
        line = f"- [{item.title}]({item.url}) - {item.source_name}; state={item.state}"
        snippet = _summary_snippet(item.summary)
        if snippet:
            line += f"; summary: {snippet}"
        rendered.append(line)
    return rendered


def _render_failures(failures: tuple[SourceHealthEntry, ...]) -> list[str]:
    if not failures:
        return ["- None."]
    return [
        f"- {failure.source_id} at {failure.checked_at}: {failure.message}"
        for failure in failures
    ]


def _summary_snippet(summary: str, limit: int = 180) -> str:
    cleaned = " ".join(summary.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _format_state_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{state}={count}" for state, count in sorted(counts.items()))
