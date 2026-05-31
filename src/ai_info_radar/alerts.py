from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .classifier import ClassificationRules, classify_item
from .events import merge_events
from .models import AlertDecision, AlertDeliveryResult, AlertMessage, StoredItem
from .notifiers import send_feishu_webhook
from .store import RadarStore


@dataclass(frozen=True)
class AlertRunResult:
    status: str
    message: str
    sent: bool = False
    alert_key: str | None = None
    short_id: str | None = None
    title: str | None = None
    payload: dict[str, object] | None = None


AlertSender = Callable[[str, AlertMessage], AlertDeliveryResult]


def send_next_critical_alert(
    *,
    db_path: str | Path,
    webhook_url: str | None,
    rules: ClassificationRules | None = None,
    sender: AlertSender | None = None,
    timeout_seconds: float = 10.0,
) -> AlertRunResult:
    with RadarStore(db_path) as store:
        merge_events(store)
        candidate = _select_candidate(store, rules=rules)
        if candidate is None:
            return AlertRunResult(status="skipped", message="没有待发送的强提醒")

        event_key, item, decision = candidate
        supporting_sources = store.event_supporting_sources(event_key, exclude_item_id=item.id)
        alert_message = build_alert_message(
            item,
            decision,
            supporting_sources=supporting_sources,
        )

        if not webhook_url:
            return AlertRunResult(
                status="blocked",
                message="缺少 FEISHU_WEBHOOK_URL",
                alert_key=f"event:{event_key}",
                short_id=alert_message.short_id,
                title=alert_message.title,
                payload=None,
            )

        effective_sender = sender or (
            lambda url, message: send_feishu_webhook(
                url,
                message,
                timeout_seconds=timeout_seconds,
            )
        )
        delivery = effective_sender(webhook_url, alert_message)
        if not delivery.ok:
            return AlertRunResult(
                status="failed",
                message=delivery.message or "飞书 Webhook 发送失败",
                alert_key=f"event:{event_key}",
                short_id=alert_message.short_id,
                title=alert_message.title,
                payload=delivery.payload,
            )

        store.record_alert(
            alert_key=f"event:{event_key}",
            item_id=item.id,
            fingerprint=item.fingerprint,
            notifier="feishu",
            status="sent",
            message=delivery.message,
        )
        return AlertRunResult(
            status="sent",
            message="飞书提醒已发送",
            sent=True,
            alert_key=f"event:{event_key}",
            short_id=alert_message.short_id,
            title=alert_message.title,
            payload=delivery.payload,
        )


def build_alert_message(
    item: StoredItem,
    decision: AlertDecision,
    *,
    supporting_sources: tuple[str, ...] = (),
) -> AlertMessage:
    why = "；".join(_localize_reason(reason) for reason in decision.reasons)
    return AlertMessage(
        short_id=item.fingerprint[:10],
        title=item.title,
        source=f"{item.source_name} ({item.vendor})",
        authority=item.authority_level,
        why_it_matters=why,
        original_link=item.url,
        supporting_sources=supporting_sources,
        matched_terms=decision.matched_terms,
    )


def _localize_reason(reason: str) -> str:
    if reason.startswith("official authority: "):
        return "官方来源：" + reason.removeprefix("official authority: ")
    if reason.startswith("candidate authority: "):
        return "候选来源：" + reason.removeprefix("candidate authority: ")
    if reason.startswith("high-signal content type: "):
        return "高信号内容类型：" + reason.removeprefix("high-signal content type: ")
    return {
        "breaking change": "破坏性变更",
        "migration impact": "迁移影响",
        "deprecation or removal": "弃用或移除",
        "pricing or limit change": "价格或限额变化",
        "model or product release": "模型或产品发布",
        "security or availability event": "安全或可用性事件",
        "developer-tool workflow impact": "开发工具工作流影响",
    }.get(reason, reason)


def _select_candidate(
    store: RadarStore,
    *,
    rules: ClassificationRules | None = None,
) -> tuple[str, StoredItem, AlertDecision] | None:
    candidates: list[tuple[str, StoredItem, AlertDecision]] = []
    for event in store.list_events():
        alert_key = f"event:{event.event_key}"
        if store.alert_exists(alert_key):
            continue
        event_candidates: list[tuple[StoredItem, AlertDecision]] = []
        for item in store.event_items(event.event_key):
            if item.state != "new":
                continue
            decision = classify_item(item, rules)
            if decision.should_alert:
                event_candidates.append((item, decision))
        if not event_candidates:
            continue
        item, decision = max(
            event_candidates,
            key=lambda pair: (
                pair[1].score,
                pair[0].published_at or "",
                pair[0].id,
            ),
        )
        candidates.append((event.event_key, item, decision))

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda pair: (
            pair[2].score,
            pair[1].published_at or "",
            pair[1].id,
        ),
    )
