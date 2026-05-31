from __future__ import annotations

from dataclasses import dataclass

from .classifier import ClassificationRules, classify_item
from .events import merge_events
from .models import AlertDecision, StoredItem
from .store import RadarStore


USER_MANAGED_STATES = {"ignored", "read", "saved"}
SURFACE_DONE_STATES = {"alerted", "daily", "digested", "ignored", "read"}
OUTCOMES = ("would-alert", "would-digest", "candidate", "ignored")


@dataclass(frozen=True)
class RuleTestItem:
    item: StoredItem
    decision: AlertDecision
    outcome: str


@dataclass(frozen=True)
class ReclassifyUpdate:
    item: StoredItem
    decision: AlertDecision
    outcome: str
    previous_state: str
    new_state: str
    changed: bool
    preserved: bool


def test_recent_items(
    store: RadarStore,
    *,
    rules: ClassificationRules,
    limit: int = 20,
) -> list[RuleTestItem]:
    return [
        RuleTestItem(
            item=item,
            decision=decision,
            outcome=effective_outcome(item, decision, rules),
        )
        for item in store.list_recent_items(limit=limit)
        for decision in (classify_item(item, rules),)
    ]


def reclassify_recent_items(
    store: RadarStore,
    *,
    rules: ClassificationRules,
    limit: int = 20,
    include_user_states: bool = False,
) -> list[ReclassifyUpdate]:
    merge_events(store)
    updates: list[ReclassifyUpdate] = []
    for item in store.list_recent_items(limit=limit):
        decision = classify_item(item, rules)
        outcome = base_outcome(item, decision, rules)
        preserved = item.state in USER_MANAGED_STATES and not include_user_states
        new_state = item.state if preserved else desired_state(store, item, outcome)
        changed = new_state != item.state
        if changed:
            store.set_item_state_by_id(item.id, new_state)
        updates.append(
            ReclassifyUpdate(
                item=item,
                decision=decision,
                outcome=outcome,
                previous_state=item.state,
                new_state=new_state,
                changed=changed,
                preserved=preserved,
            )
        )
    return updates


def effective_outcome(
    item: StoredItem,
    decision: AlertDecision,
    rules: ClassificationRules | None = None,
) -> str:
    if item.state in SURFACE_DONE_STATES:
        return "ignored"
    return base_outcome(item, decision, rules)


def base_outcome(
    item: StoredItem,
    decision: AlertDecision,
    rules: ClassificationRules | None = None,
) -> str:
    active_rules = rules
    if decision.should_alert:
        return "would-alert"
    if decision.severity == "candidate":
        return "candidate"
    if active_rules is not None:
        digest_authority = item.authority_level in active_rules.official_authority_levels
        digest_context = item.content_type in active_rules.high_signal_content_types
        if digest_authority or digest_context:
            return "would-digest"
    elif item.authority_level in {"official", "official_github", "status"}:
        return "would-digest"
    return "ignored"


def desired_state(store: RadarStore, item: StoredItem, outcome: str) -> str:
    if _previous_alert_exists(store, item):
        return "alerted"
    if outcome == "ignored":
        return "ignored"
    return "new"


def summarize_outcomes(items: list[RuleTestItem] | list[ReclassifyUpdate]) -> dict[str, int]:
    counts = {outcome: 0 for outcome in OUTCOMES}
    for item in items:
        counts[item.outcome] = counts.get(item.outcome, 0) + 1
    return counts


def _previous_alert_exists(store: RadarStore, item: StoredItem) -> bool:
    if store.item_alert_exists(item.id):
        return True
    event_key = store.event_key_for_item(item.id)
    return event_key is not None and store.alert_exists(f"event:{event_key}")
