from __future__ import annotations

from collections.abc import Iterable

from .models import FocusConfig, RadarItem, ScoringConfig


WORLD_SIGNALS = {
    "frontier": 1.4,
    "model": 1.3,
    "reasoning": 1.1,
    "multimodal": 1.1,
    "benchmark": 1.0,
    "eval": 1.0,
    "release": 0.9,
    "paper": 0.9,
    "agent": 1.1,
    "api": 0.7,
    "open source": 0.7,
    "browser use": 0.7,
    "tool use": 0.7,
    "policy": 0.7,
    "safety": 0.7,
}

LEARNING_SIGNALS = {
    "paper": 1.3,
    "concept": 1.2,
    "architecture": 1.1,
    "mechanism": 1.0,
    "benchmark": 0.9,
    "evaluation": 0.9,
    "guide": 0.8,
    "analysis": 0.8,
    "dataset": 0.8,
    "memory": 0.7,
    "rag": 0.7,
}

PRACTICE_SIGNALS = {
    "github": 1.3,
    "repo": 1.2,
    "browser use": 1.2,
    "sdk": 1.1,
    "tool use": 1.0,
    "mcp": 1.0,
    "api": 1.0,
    "demo": 1.0,
    "notebook": 0.9,
    "install": 0.9,
    "open source": 0.9,
    "playwright": 0.8,
    "automation": 0.8,
    "example": 0.7,
}

TIER_BONUS = {
    "primary": 0.7,
    "strong_signal": 0.4,
    "lead": 0.0,
}


def score_items(items: list[RadarItem], focus: FocusConfig, scoring: ScoringConfig) -> list[RadarItem]:
    for item in items:
        score_item(item, focus, scoring)
    return items


def score_item(item: RadarItem, focus: FocusConfig, scoring: ScoringConfig) -> RadarItem:
    text = item.text_for_matching
    source_bonus = TIER_BONUS.get(item.source_tier, 0.0)

    item.world_value = _clamp(4.0 + source_bonus + (_keyword_score(text, WORLD_SIGNALS) * 1.15))
    item.learning_value = _clamp(3.5 + _keyword_score(text, LEARNING_SIGNALS))
    item.practice_value = _clamp(3.0 + (_keyword_score(text, PRACTICE_SIGNALS) * 1.25))
    item.current_focus_fit = _clamp(_focus_score(text, focus))
    item.related_focus_topics = _matched_keywords(text, focus.keywords)

    weights = scoring.weights
    item.final_score = _clamp(
        item.world_value * weights.get("world_value", 0.35)
        + item.learning_value * weights.get("learning_value", 0.25)
        + item.practice_value * weights.get("practice_value", 0.20)
        + item.current_focus_fit * weights.get("current_focus_fit", 0.20)
    )
    item.labels = _labels_for(item, scoring)
    return item


def _keyword_score(text: str, signals: dict[str, float]) -> float:
    return sum(weight for keyword, weight in signals.items() if keyword in text)


def _focus_score(text: str, focus: FocusConfig) -> float:
    primary_matches = _matched_keywords(text, focus.keywords)
    secondary_matches = _matched_keywords(text, focus.secondary_interests)
    if not primary_matches and not secondary_matches:
        return 1.0
    score = 2.0
    score += min(5.0, len(primary_matches) * 1.4 * focus.weight)
    score += min(2.0, len(secondary_matches) * 0.7)
    return score


def _matched_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword.lower() in text]


def _labels_for(item: RadarItem, scoring: ScoringConfig) -> list[str]:
    thresholds = scoring.thresholds
    labels: list[str] = []
    if item.final_score >= thresholds.get("must_read", 8.0):
        labels.append("must_read")
    if item.learning_value >= thresholds.get("worth_learning", 6.5):
        labels.append("worth_learning")
    if item.practice_value >= thresholds.get("worth_trying", 6.5):
        labels.append("worth_trying")
    if not labels and item.final_score >= thresholds.get("monitor", 5.0):
        labels.append("monitor")
    if not labels:
        labels.append("ignore_for_now")
    return labels


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return round(max(low, min(high, value)), 2)
