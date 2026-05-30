from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .classifier import classify_item
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
    sender: AlertSender | None = None,
    timeout_seconds: float = 10.0,
) -> AlertRunResult:
    with RadarStore(db_path) as store:
        candidate = _select_candidate(store)
        if candidate is None:
            return AlertRunResult(status="skipped", message="no unalerted critical item")

        item, decision = candidate
        supporting_sources = store.supporting_sources_for(title=item.title, exclude_item_id=item.id)
        alert_message = build_alert_message(
            item,
            decision,
            supporting_sources=supporting_sources,
        )

        if not webhook_url:
            return AlertRunResult(
                status="blocked",
                message="missing FEISHU_WEBHOOK_URL",
                alert_key=decision.alert_key,
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
                message=delivery.message or "Feishu webhook delivery failed",
                alert_key=decision.alert_key,
                short_id=alert_message.short_id,
                title=alert_message.title,
                payload=delivery.payload,
            )

        store.record_alert(
            alert_key=decision.alert_key,
            item_id=item.id,
            fingerprint=item.fingerprint,
            notifier="feishu",
            status="sent",
            message=delivery.message,
        )
        return AlertRunResult(
            status="sent",
            message="Feishu alert sent",
            sent=True,
            alert_key=decision.alert_key,
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
    why = "; ".join(decision.reasons)
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


def _select_candidate(store: RadarStore) -> tuple[StoredItem, AlertDecision] | None:
    candidates: list[tuple[StoredItem, AlertDecision]] = []
    for item in store.list_items():
        decision = classify_item(item)
        if not decision.should_alert or store.alert_exists(decision.alert_key):
            continue
        candidates.append((item, decision))

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda pair: (
            pair[1].score,
            pair[0].published_at or "",
            pair[0].id,
        ),
    )
