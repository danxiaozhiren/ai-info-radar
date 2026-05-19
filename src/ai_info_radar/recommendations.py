from __future__ import annotations

from collections.abc import Iterable

from .models import RadarItem


SOURCE_ROLES = {
    "primary": "fact_anchor",
    "strong_signal": "signal_source",
    "lead": "lead_source",
}

COVERAGE_AREA_LABELS = {
    "models_capabilities": "models and capabilities",
    "research_papers": "research and papers",
    "tools_products": "tools and products",
    "developer_ecosystem": "developer ecosystem",
    "open_source": "open source",
    "infrastructure": "infrastructure and deployment",
    "evals_benchmarks": "evals and benchmarks",
    "safety_policy": "safety and policy",
    "industry": "industry and adoption",
    "other": "other AI signal",
}

ACTION_LABELS = {
    "read": "read",
    "verify": "verify",
    "study": "study",
    "try": "try",
    "monitor": "monitor",
    "ignore": "ignore",
}

AREA_KEYWORDS = {
    "safety_policy": {
        "safety",
        "policy",
        "regulation",
        "regulatory",
        "security",
        "authorization",
        "cve",
        "risk",
    },
    "evals_benchmarks": {
        "eval",
        "evaluation",
        "benchmark",
        "benchmarks",
        "lmarena",
        "arena",
        "helm",
    },
    "research_papers": {
        "arxiv",
        "paper",
        "papers",
        "research",
        "abstract",
        "dataset",
        "method",
    },
    "tools_products": {
        "product",
        "products",
        "release",
        "changelog",
        "api",
        "sdk",
        "cli",
        "tool",
        "tools",
    },
    "developer_ecosystem": {
        "developer",
        "developer tools",
        "mcp",
        "codex",
        "claude code",
        "browser use",
        "playwright",
        "automation",
        "agent",
        "agentic",
    },
    "open_source": {
        "github",
        "open source",
        "open-source",
        "repo",
        "repository",
    },
    "infrastructure": {
        "deployment",
        "inference",
        "serving",
        "latency",
        "gpu",
        "cuda",
        "quantization",
        "memory",
    },
    "models_capabilities": {
        "model",
        "models",
        "frontier",
        "reasoning",
        "multimodal",
        "llm",
        "gpt",
        "claude",
        "gemini",
    },
    "industry": {
        "industry",
        "adoption",
        "business",
        "company",
        "enterprise",
        "funding",
        "customer",
    },
}

RAW_CATEGORY_AREAS = {
    "models": "models_capabilities",
    "model": "models_capabilities",
    "papers": "research_papers",
    "paper": "research_papers",
    "research": "research_papers",
    "developer_tools": "developer_ecosystem",
    "tools": "tools_products",
    "products": "tools_products",
    "safety_policy": "safety_policy",
    "policy": "safety_policy",
    "evals": "evals_benchmarks",
    "benchmarks": "evals_benchmarks",
    "infrastructure": "infrastructure",
    "industry": "industry",
}


def enrich_recommendations(items: list[RadarItem]) -> list[RadarItem]:
    for item in items:
        enrich_recommendation(item)
    return items


def enrich_recommendation(item: RadarItem) -> RadarItem:
    if not item.source_role:
        item.source_role = SOURCE_ROLES.get(item.source_tier, "lead_source")
    if not item.coverage_area:
        item.coverage_area = classify_coverage_area(item)
    item.action_type = choose_action_type(item)
    item.recommendation_reason = build_recommendation_reason(item)
    return item


def classify_coverage_area(item: RadarItem) -> str:
    raw_category = item.raw_category.lower().replace("_", " ").strip()
    mapped = RAW_CATEGORY_AREAS.get(raw_category.replace(" ", "_"))
    if mapped:
        return mapped

    text = item.text_for_matching
    source = item.source_name.lower()
    combined = f"{source} {text}"
    for area, keywords in AREA_KEYWORDS.items():
        if _contains_any(combined, keywords):
            return area
    return "other"


def choose_action_type(item: RadarItem) -> str:
    if "needs_verification" in item.labels:
        return "verify"
    if "ignore_for_now" in item.labels:
        return "ignore"
    if "worth_trying" in item.labels:
        return "try"
    if "worth_learning" in item.labels:
        return "study"
    if "must_read" in item.labels or item.world_value >= 7.5:
        return "read"
    return "monitor"


def build_recommendation_reason(item: RadarItem) -> str:
    reasons: list[str] = []
    if item.source_role == "fact_anchor":
        reasons.append("primary source can anchor facts")
    elif item.source_role == "signal_source":
        reasons.append("strong signal source still needs source check")
    else:
        reasons.append("lead source should be verified before acting")

    if item.world_value >= 7:
        reasons.append("high broad AI importance")
    if item.current_focus_fit >= 5 or item.related_focus_topics:
        reasons.append("matches the current focus lens")
    if item.practice_value >= 6.5:
        reasons.append("has hands-on practice potential")
    if item.learning_value >= 6.5:
        reasons.append("has clear learning value")

    if not reasons:
        reasons.append("moderate signal worth monitoring")
    return "; ".join(_dedupe_keep_order(reasons))


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
