from __future__ import annotations

from dataclasses import dataclass

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
        terms=("pricing", "price", "rate limit", "rate-limit", "quota"),
        score=30,
        reason="pricing or limit change",
    ),
    KeywordRule(
        name="model_release",
        terms=("model release", "launch", "new model", "sonnet", "opus", "haiku"),
        score=24,
        reason="model or product release",
    ),
    KeywordRule(
        name="security_or_outage",
        terms=("security", "vulnerability", "incident", "outage", "recovery"),
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


def classify_item(item: StoredItem) -> AlertDecision:
    text = "\n".join((item.title, item.summary, item.content_type)).lower()
    matched_terms: list[str] = []
    reasons: list[str] = []
    score = 0

    is_official = item.authority_level in OFFICIAL_AUTHORITY_LEVELS
    is_candidate_source = item.authority_level in CANDIDATE_AUTHORITY_LEVELS
    if is_official:
        score += 30
        reasons.append(f"official authority: {item.authority_level}")
    elif is_candidate_source:
        reasons.append(f"candidate authority: {item.authority_level}")

    has_high_signal_context = item.content_type in HIGH_SIGNAL_CONTENT_TYPES
    if has_high_signal_context:
        score += 12
        reasons.append(f"high-signal content type: {item.content_type}")

    for rule in KEYWORD_RULES:
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
