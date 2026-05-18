from __future__ import annotations

from .models import RadarItem


def verify_items(items: list[RadarItem]) -> list[RadarItem]:
    for item in items:
        verify_item(item)
    return items


def verify_item(item: RadarItem) -> RadarItem:
    if item.source_tier == "primary":
        item.confidence = "high"
        item.verification_status = "primary_source_supported"
    elif item.source_tier == "strong_signal":
        item.confidence = "medium"
        item.verification_status = "strong_signal_needs_primary_check"
        _append_label(item, "needs_verification")
    else:
        item.confidence = "low"
        item.verification_status = "lead_source_needs_verification"
        _append_label(item, "needs_verification")

    if not item.url:
        item.confidence = "low"
        item.verification_status = "missing_source_url"
        _append_label(item, "needs_verification")

    if not item.claims and item.summary:
        item.claims = [item.summary]
    return item


def _append_label(item: RadarItem, label: str) -> None:
    if label not in item.labels:
        item.labels.append(label)
