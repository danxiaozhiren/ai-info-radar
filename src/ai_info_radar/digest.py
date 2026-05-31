from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
            message="日报已写入；未配置 FEISHU_WEBHOOK_URL",
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
            message=delivery.message or "飞书日报发送失败",
            report_path=report_path,
            sent=False,
            payload=delivery.payload or payload,
            marked_digested=marked,
        )

    return DigestRunResult(
        status="sent",
        message="飞书日报已发送",
        report_path=report_path,
        sent=True,
        payload=delivery.payload or payload,
        marked_digested=marked,
    )


def build_digest_content(store: RadarStore, report_date: date) -> DigestContent:
    merge_events(store)
    items = store.list_items()
    alerts = tuple(
        alert
        for alert in store.list_alert_history(
            exclude_item_states={"daily", "digested", "ignored", "read", "saved"}
        )
        if _iso_date_matches(alert.alerted_at, report_date)
    )
    alerted_item_ids = {alert.item_id for alert in alerts}
    saved_items = tuple(item for item in items if item.state == "saved")
    worth_reading_items = tuple(
        item
        for item in items
        if item.state == "new"
        and item.id not in alerted_item_ids
        and _item_report_date_matches(item, report_date)
    )
    source_failures = tuple(
        failure
        for failure in store.list_source_failures()
        if _iso_date_matches(failure.checked_at, report_date)
    )
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
        f"# AI 情报雷达日报 - {content.report_date.isoformat()}",
        "",
        "## 已提醒",
        *_render_alerts(content.alerted_items),
        "",
        "## 值得阅读",
        *_render_items(content.worth_reading_items),
        "",
        "## 已保存",
        *_render_items(content.saved_items),
        "",
        "## 来源失败",
        *_render_failures(content.source_failures),
        "",
        "## 过滤统计",
        f"- 总条目数：{content.total_items}",
        f"- 已提醒：{len(content.alerted_items)}",
        f"- 值得阅读：{len(content.worth_reading_items)}",
        f"- 已保存：{len(content.saved_items)}",
        f"- 来源失败：{len(content.source_failures)}",
        f"- 本次标记为已入日报：{content.marked_digested}",
        f"- 状态统计：{_format_state_counts(content.state_counts)}",
        "",
    ]
    return "\n".join(lines)


def render_digest_text(content: DigestContent) -> str:
    lines = [
        f"AI 情报雷达日报 - {content.report_date.isoformat()}",
        (
            f"已提醒 {len(content.alerted_items)} | "
            f"值得阅读 {len(content.worth_reading_items)} | "
            f"已保存 {len(content.saved_items)} | "
            f"来源失败 {len(content.source_failures)}"
        ),
    ]
    if content.alerted_items:
        lines.append("已提醒：")
        lines.extend(f"- {alert.title} ({alert.source_name}) {alert.url}" for alert in content.alerted_items[:5])
    if content.worth_reading_items:
        lines.append("值得阅读：")
        lines.extend(f"- {item.title} ({item.source_name}) {item.url}" for item in content.worth_reading_items[:8])
    if content.saved_items:
        lines.append("已保存：")
        lines.extend(f"- {item.title} ({item.source_name}) {item.url}" for item in content.saved_items[:5])
    if content.source_failures:
        lines.append("来源失败：")
        lines.extend(f"- {failure.source_id}: {failure.message}" for failure in content.source_failures[:5])
    lines.append(f"本次标记为已入日报：{content.marked_digested}")
    return "\n".join(lines)


def _included_item_ids(content: DigestContent) -> list[int]:
    ids = [alert.item_id for alert in content.alerted_items]
    ids.extend(item.id for item in content.worth_reading_items)
    ids.extend(item.id for item in content.saved_items)
    return list(dict.fromkeys(ids))


def _render_alerts(alerts: tuple[AlertHistoryEntry, ...]) -> list[str]:
    if not alerts:
        return ["- 无。"]
    rendered = []
    for alert in alerts:
        line = f"- [{alert.title}]({alert.url}) - {alert.source_name}；提醒时间：{alert.alerted_at}"
        if alert.supporting_sources:
            line += f"；支持来源：{', '.join(alert.supporting_sources)}"
        rendered.append(line)
    return rendered


def _render_items(items: tuple[StoredItem, ...]) -> list[str]:
    if not items:
        return ["- 无。"]
    rendered = []
    for item in items:
        line = f"- [{item.title}]({item.url}) - {item.source_name}；状态={_localize_state(item.state)}"
        snippet = _summary_snippet(item.summary)
        if snippet:
            line += f"；摘要：{snippet}"
        rendered.append(line)
    return rendered


def _render_failures(failures: tuple[SourceHealthEntry, ...]) -> list[str]:
    if not failures:
        return ["- 无。"]
    return [
        f"- {failure.source_id} 于 {failure.checked_at}：{failure.message}"
        for failure in failures
    ]


def _summary_snippet(summary: str, limit: int = 180) -> str:
    cleaned = " ".join(summary.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _format_state_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "无"
    return ", ".join(f"{_localize_state(state)}={count}" for state, count in sorted(counts.items()))


def _localize_state(state: str) -> str:
    return {
        "new": "新条目",
        "alerted": "已提醒",
        "daily": "已入日报",
        "read": "已读",
        "saved": "已保存",
        "ignored": "已忽略",
        "digested": "已汇总",
    }.get(state, state)


def _item_report_date_matches(item: StoredItem, report_date: date) -> bool:
    effective_date = item.published_at or item.detected_at
    return _iso_date_matches(effective_date, report_date)


def _iso_date_matches(value: str | None, report_date: date) -> bool:
    parsed = _parse_iso_date(value)
    return parsed == report_date


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) == 10:
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            return None

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.date()
