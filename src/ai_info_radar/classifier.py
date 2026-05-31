from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AlertDecision, StoredItem


OFFICIAL_AUTHORITY_LEVELS = {"official", "official_github", "status"}
CANDIDATE_AUTHORITY_LEVELS = {"aggregator", "media", "social"}
HIGH_SIGNAL_CONTENT_TYPES = {
    "api_changelog",
    "aggregator_candidate",
    "developer_changelog",
    "engineering",
    "model_list",
    "pricing",
    "status_incident",
}


@dataclass(frozen=True)
class KeywordRule:
    name: str
    terms: tuple[str, ...]
    score: int
    reason: str


@dataclass(frozen=True)
class ClassificationRules:
    official_authority_levels: tuple[str, ...]
    candidate_authority_levels: tuple[str, ...]
    high_signal_content_types: tuple[str, ...]
    keyword_rules: tuple[KeywordRule, ...]


class RulesError(ValueError):
    pass


KEYWORD_RULES = (
    KeywordRule(
        name="breaking_change",
        terms=("breaking change", "breaking changes"),
        score=40,
        reason="breaking change",
    ),
    KeywordRule(
        name="migration",
        terms=("migration", "migrated", "migrate"),
        score=28,
        reason="migration impact",
    ),
    KeywordRule(
        name="deprecation",
        terms=("deprecated", "deprecation", "removed"),
        score=32,
        reason="deprecation or removal",
    ),
    KeywordRule(
        name="pricing_or_limits",
        terms=(
            "pricing",
            "price",
            "input price",
            "output price",
            "rate limit",
            "rate-limit",
            "quota",
            "tokens per minute",
        ),
        score=30,
        reason="pricing or limit change",
    ),
    KeywordRule(
        name="model_release",
        terms=(
            "model release",
            "launch",
            "new model",
            "model:",
            "capabilities:",
            "context:",
            "sonnet",
            "opus",
            "haiku",
        ),
        score=24,
        reason="model or product release",
    ),
    KeywordRule(
        name="security_or_outage",
        terms=(
            "security",
            "vulnerability",
            "incident",
            "outage",
            "partial outage",
            "major outage",
            "degraded",
            "degradation",
            "elevated errors",
            "investigating",
            "monitoring",
            "resolved",
            "recovered",
            "recovery",
        ),
        score=36,
        reason="security or availability event",
    ),
    KeywordRule(
        name="developer_tooling",
        terms=("mcp", "agent workflow", "permission", "sandbox", "hooks schema"),
        score=20,
        reason="developer-tool workflow impact",
    ),
)

DEFAULT_RULES = ClassificationRules(
    official_authority_levels=tuple(sorted(OFFICIAL_AUTHORITY_LEVELS)),
    candidate_authority_levels=tuple(sorted(CANDIDATE_AUTHORITY_LEVELS)),
    high_signal_content_types=tuple(sorted(HIGH_SIGNAL_CONTENT_TYPES)),
    keyword_rules=KEYWORD_RULES,
)


def load_rules(path: str | Path | None = None) -> ClassificationRules:
    if path is None:
        return DEFAULT_RULES
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RulesError("Rules config must be a JSON object.")
    return ClassificationRules(
        official_authority_levels=_string_tuple(raw, "official_authority_levels"),
        candidate_authority_levels=_string_tuple(raw, "candidate_authority_levels"),
        high_signal_content_types=_string_tuple(raw, "high_signal_content_types"),
        keyword_rules=_keyword_rules(raw.get("keyword_rules")),
    )


def classify_item(item: StoredItem, rules: ClassificationRules | None = None) -> AlertDecision:
    active_rules = rules or DEFAULT_RULES
    text = "\n".join((item.title, item.summary, item.content_type)).lower()
    matched_terms: list[str] = []
    reasons: list[str] = []
    score = 0

    is_official = item.authority_level in active_rules.official_authority_levels
    is_candidate_source = item.authority_level in active_rules.candidate_authority_levels
    if is_official:
        score += 30
        reasons.append(f"official authority: {item.authority_level}")
    elif is_candidate_source:
        reasons.append(f"candidate authority: {item.authority_level}")

    has_high_signal_context = item.content_type in active_rules.high_signal_content_types
    if has_high_signal_context:
        score += 12
        reasons.append(f"high-signal content type: {item.content_type}")

    for rule in active_rules.keyword_rules:
        found_terms = tuple(term for term in rule.terms if term in text)
        if not found_terms:
            continue
        score += rule.score
        matched_terms.extend(found_terms)
        reasons.append(rule.reason)

    should_alert = is_official and has_high_signal_context and bool(matched_terms)
    severity = "critical" if should_alert else "candidate" if is_candidate_source and matched_terms else "none"
    return AlertDecision(
        alert_key=f"item:{item.fingerprint}",
        should_alert=should_alert,
        severity=severity,
        score=score,
        reasons=tuple(dict.fromkeys(reasons)),
        matched_terms=tuple(dict.fromkeys(matched_terms)),
    )


def _string_tuple(raw: dict[str, Any], field: str) -> tuple[str, ...]:
    value = raw.get(field)
    if not isinstance(value, list):
        raise RulesError(f"Rules field '{field}' must be a list.")
    strings = tuple(_clean_string(item, field) for item in value)
    if not strings:
        raise RulesError(f"Rules field '{field}' cannot be empty.")
    return strings


def _keyword_rules(value: Any) -> tuple[KeywordRule, ...]:
    if not isinstance(value, list) or not value:
        raise RulesError("Rules field 'keyword_rules' must be a non-empty list.")
    rules: list[KeywordRule] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise RulesError(f"Keyword rule at index {index} must be an object.")
        name = _clean_string(entry.get("name"), f"keyword_rules[{index}].name")
        terms_value = entry.get("terms")
        if not isinstance(terms_value, list) or not terms_value:
            raise RulesError(f"Keyword rule '{name}' terms must be a non-empty list.")
        terms = tuple(_clean_string(term, f"keyword_rules[{index}].terms") for term in terms_value)
        try:
            score = int(entry["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RulesError(f"Keyword rule '{name}' score must be an integer.") from exc
        reason = _clean_string(entry.get("reason"), f"keyword_rules[{index}].reason")
        rules.append(KeywordRule(name=name, terms=terms, score=score, reason=reason))
    return tuple(rules)


def _clean_string(value: Any, field: str) -> str:
    cleaned = str(value).strip().lower() if value is not None else ""
    if not cleaned:
        raise RulesError(f"Rules field '{field}' cannot be empty.")
    return cleaned
