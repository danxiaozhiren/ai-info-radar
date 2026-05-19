from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .models import RadarItem, RadarRun

REPORT_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

ZH_SECTIONS = [
    ("Models And Capabilities", "模型与能力", {"models_capabilities"}),
    ("Tools And Products", "工具与产品", {"tools_products", "developer_ecosystem"}),
    ("Open Source And Developer Ecosystem", "开源与开发者生态", {"open_source", "developer_ecosystem"}),
    ("Papers And Concepts", "论文与概念", {"research_papers", "evals_benchmarks"}),
    ("Industry And Trends", "行业与趋势", {"industry", "safety_policy", "infrastructure"}),
]

LABELS_ZH = {
    "must_read": "必须关注",
    "worth_learning": "值得学习",
    "worth_trying": "值得动手",
    "monitor": "持续观察",
    "ignore_for_now": "暂时忽略",
    "needs_verification": "需要核验",
}

TIER_ZH = {
    "primary": "一手来源",
    "strong_signal": "强信号源",
    "lead": "线索源",
}

CONFIDENCE_ZH = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

COVERAGE_ZH = {
    "models_capabilities": "模型与能力",
    "research_papers": "论文与研究",
    "tools_products": "工具与产品",
    "developer_ecosystem": "开发者生态",
    "open_source": "开源生态",
    "infrastructure": "基础设施与部署",
    "evals_benchmarks": "评测与基准",
    "safety_policy": "安全与政策",
    "industry": "行业与采用",
    "other": "其他 AI 信号",
}

SOURCE_ROLE_ZH = {
    "fact_anchor": "事实锚点",
    "signal_source": "强信号源",
    "lead_source": "线索源",
}

ACTION_ZH = {
    "read": "阅读",
    "verify": "核验",
    "study": "学习",
    "try": "动手试验",
    "monitor": "观察",
    "ignore": "暂时忽略",
}

REASON_ZH = {
    "primary source can anchor facts": "一手来源可作为事实锚点",
    "strong signal source still needs source check": "强信号源仍需回到原始来源确认",
    "lead source should be verified before acting": "线索源需要先核验再行动",
    "high broad AI importance": "具备较高 AI 全局重要性",
    "matches the current focus lens": "匹配当前关注重点",
    "has hands-on practice potential": "具备动手实践价值",
    "has clear learning value": "具备明确学习价值",
    "moderate signal worth monitoring": "中等信号，适合继续观察",
}


def render_daily_radar(run: RadarRun, language: str = "zh") -> str:
    if language == "zh":
        return _render_daily_radar_zh(run)
    return _render_daily_radar_en(run)


def _render_daily_radar_zh(run: RadarRun) -> str:
    lines = [
        "# AI 每日雷达",
        "",
        f"雷达日期：{_run_report_date(run)}（{run.timezone_name}）",
        "",
        f"生成时间：{_format_datetime_for_report(run.generated_at)}",
        "",
    ]
    _append_fetch_notes(lines, run, language="zh")

    today_items = _bucket_items(run, "today")
    backfill_items = _bucket_items(run, "backfill")[:5]
    verification_items = _bucket_items(run, "needs_verification")[:5]

    used_ids: set[str] = set()
    lines.extend(["## 今日新增", ""])
    _append_items_or_empty(lines, today_items[:3], used_ids, language="zh", empty="本日暂未筛出发布/更新发生在雷达日期内的高信号条目。")

    for section_key, title, coverage_areas in ZH_SECTIONS:
        section_items = [
            item
            for item in today_items
            if item.id not in used_ids and _matches_section(item, section_key, coverage_areas)
        ][:4]
        lines.extend([f"## {title}", ""])
        _append_items_or_empty(lines, section_items, used_ids, language="zh", empty="本区暂未筛出高信号条目。")

    lines.extend(["## 近期补录", ""])
    if backfill_items:
        for item in backfill_items:
            lines.append(
                f"- {_display_title(item)}（发布/更新 {_item_date(item)}；"
                f"{_coverage_label(item, 'zh')}；建议：{_action_label(item, 'zh')}）"
            )
    else:
        lines.append("- 暂无近期补录。")
    lines.append("")

    lines.extend(["## 待核验线索", ""])
    _append_items_or_empty(lines, verification_items, set(), language="zh", empty="暂无需要单独核验的线索。")

    focus_items = [
        item for item in run.items if item.current_focus_fit >= 4.0 or item.related_focus_topics
    ][:5]
    lines.extend(["## 当前焦点", ""])
    if focus_items:
        for item in focus_items:
            topics = ", ".join(item.related_focus_topics) or "匹配次级兴趣"
            lines.append(f"- {_display_title(item)}（{topics}，{_item_date(item)}）")
    else:
        lines.append("- 暂无强相关焦点条目。")
    lines.append("")

    ignored = [item for item in run.items if "ignore_for_now" in item.labels][:5]
    lines.extend(["## 暂时忽略", ""])
    if ignored:
        for item in ignored:
            lines.append(f"- {_display_title(item)}（{item.final_score:.1f}/10，{_item_date(item)}）")
    else:
        lines.append("- 本次没有明确低价值条目；继续控制来源数量。")
    lines.append("")

    lines.extend(["## 行动建议", ""])
    actions = _actions_for(run.items, language="zh")
    lines.extend(f"- {action}" for action in actions) if actions else lines.append("- 暂无行动候选。")
    lines.append("")
    return "\n".join(lines)


def _render_daily_radar_en(run: RadarRun) -> str:
    lines = [
        "# AI Daily Radar",
        "",
        f"Radar date: {_run_report_date(run)} ({run.timezone_name})",
        "",
        f"Generated: {_format_datetime_for_report(run.generated_at)}",
        "",
    ]
    _append_fetch_notes(lines, run, language="en")

    today_items = _bucket_items(run, "today")
    backfill_items = _bucket_items(run, "backfill")[:5]
    verification_items = _bucket_items(run, "needs_verification")[:5]

    used_ids: set[str] = set()
    lines.extend(["## New Today", ""])
    _append_items_or_empty(lines, today_items[:3], used_ids, language="en", empty="No high-signal items published or updated on the radar date.")

    for section_key, _, coverage_areas in ZH_SECTIONS:
        section_items = [
            item
            for item in today_items
            if item.id not in used_ids and _matches_section(item, section_key, coverage_areas)
        ][:4]
        lines.extend([f"## {section_key}", ""])
        _append_items_or_empty(lines, section_items, used_ids, language="en", empty="No high-signal items in this section.")

    lines.extend(["## Recent Backfill", ""])
    if backfill_items:
        for item in backfill_items:
            lines.append(
                f"- {_display_title(item)} (published/updated {_item_date(item)}; "
                f"{_coverage_label(item, 'en')}; action: {_action_label(item, 'en')})"
            )
    else:
        lines.append("- No recent backfill items.")
    lines.append("")

    lines.extend(["## Leads To Verify", ""])
    _append_items_or_empty(lines, verification_items, set(), language="en", empty="No separate leads need verification.")

    focus_items = [
        item for item in run.items if item.current_focus_fit >= 4.0 or item.related_focus_topics
    ][:5]
    lines.extend(["## Current Focus", ""])
    if focus_items:
        for item in focus_items:
            topics = ", ".join(item.related_focus_topics) or "secondary interest match"
            lines.append(f"- {_display_title(item)} ({topics}, {_item_date(item)})")
    else:
        lines.append("- No strong current-focus matches.")
    lines.append("")

    ignored = [item for item in run.items if "ignore_for_now" in item.labels][:5]
    lines.extend(["## Ignore For Now", ""])
    if ignored:
        for item in ignored:
            lines.append(f"- {_display_title(item)} ({item.final_score:.1f}/10, {_item_date(item)})")
    else:
        lines.append("- Nothing collected was explicitly low-value; keep source volume small.")
    lines.append("")

    lines.extend(["## Actions", ""])
    actions = _actions_for(run.items, language="en")
    lines.extend(f"- {action}" for action in actions) if actions else lines.append("- No action candidates.")
    lines.append("")
    return "\n".join(lines)


def _append_fetch_notes(lines: list[str], run: RadarRun, language: str) -> None:
    if not run.fetch_errors:
        return
    lines.extend(["## 抓取备注" if language == "zh" else "## Fetch Notes", ""])
    lines.extend(f"- {error}" for error in run.fetch_errors)
    lines.append("")


def _append_items_or_empty(
    lines: list[str],
    items: list[RadarItem],
    used_ids: set[str],
    language: str,
    empty: str,
) -> None:
    if items:
        for item in items:
            used_ids.add(item.id)
            lines.extend(_format_item(item, language=language))
    else:
        lines.append(f"- {empty}")
    lines.append("")


def _format_item(item: RadarItem, language: str) -> list[str]:
    labels = _format_labels(item.labels, language)
    source = f"[{item.source_name}]({item.url})" if item.url else item.source_name
    evidence = _shorten(item.claims[0] if item.claims else item.summary or "Collected source signal.", 360)
    why = _why_it_matters(item, language)
    uncertainty = _uncertainty(item, language)
    action = _item_action(item, language)

    if language == "zh":
        tier = TIER_ZH.get(item.source_tier, item.source_tier)
        confidence = CONFIDENCE_ZH.get(item.confidence, item.confidence)
        lines = [
            f"### {_display_title(item)}",
            "",
            f"- 来源：{source}",
            f"- 日期：发布/更新 {_item_date(item)}；抓取 {_item_date(item, use_fetched=True)}",
            f"- 可信度：{tier} | 置信度：{confidence} | 评分：{item.final_score:.1f}/10 | 标签：{labels}",
            f"- 覆盖领域：{_coverage_label(item, 'zh')} | 来源角色：{_source_role_label(item, 'zh')} | 建议：{_action_label(item, 'zh')}",
            f"- 推荐理由：{_recommendation_reason(item, 'zh')}",
            f"- 中文要点：{_summary_zh(item)}",
            f"- 原文证据：{evidence}",
            f"- 为什么重要：{why}",
            f"- 不确定性：{uncertainty}",
            f"- 建议行动：{action}",
        ]
    else:
        lines = [
            f"### {_display_title(item)}",
            "",
            f"- Source: {source}",
            f"- Date: published/updated {_item_date(item)}; fetched {_item_date(item, use_fetched=True)}",
            f"- Trust: {item.source_tier} | confidence: {item.confidence} | score: {item.final_score:.1f}/10 | labels: {labels}",
            f"- Coverage: {_coverage_label(item, 'en')} | source role: {_source_role_label(item, 'en')} | action: {_action_label(item, 'en')}",
            f"- Recommendation reason: {_recommendation_reason(item, 'en')}",
            f"- Fact: {evidence}",
            f"- Why it matters: {why}",
            f"- Uncertainty: {uncertainty}",
            f"- Action: {action}",
        ]
    lines.extend(_related_lines(item, language))
    lines.append("")
    return lines


def _bucket_items(run: RadarRun, bucket: str) -> list[RadarItem]:
    return [item for item in run.items if item.daily_bucket == bucket]


def _matches_section(item: RadarItem, section_key: str, coverage_areas: set[str]) -> bool:
    if item.coverage_area in coverage_areas:
        return True
    text = item.text_for_matching
    if section_key == "Models And Capabilities":
        return _has_any(text, {"model", "multimodal", "reasoning", "benchmark", "alignment"})
    if section_key == "Tools And Products":
        return _has_any(text, {"sdk", "api", "cli", "product", "tool", "release"})
    if section_key == "Open Source And Developer Ecosystem":
        return _has_any(text, {"github", "open source", "mcp", "developer"})
    if section_key == "Papers And Concepts":
        return item.source_name.lower().startswith("arxiv") or _has_any(text, {"paper", "abstract", "method", "dataset", "eval"})
    if section_key == "Industry And Trends":
        return _has_any(text, {"company", "enterprise", "policy", "industry", "adoption"})
    return False


def _summary_zh(item: RadarItem) -> str:
    signals = _summary_signals_zh(item)
    if signals:
        return f"这条来自 {item.source_name}，主要信息是：" + "；".join(signals[:3]) + "。"
    if item.summary:
        return item.summary
    return f"这条来自 {item.source_name}，需要结合原文判断它是否代表真实变化。"


def _summary_signals_zh(item: RadarItem) -> list[str]:
    text = item.text_for_matching
    signals: list[str] = []
    if _has_any(text, {"default model", "gpt-", "model", "models"}):
        signals.append("模型、能力或默认配置变化")
    if _has_any(text, {"mcp", "sdk", "api", "cli", "developer"}):
        signals.append("开发者工具、协议或 API 变化")
    if _has_any(text, {"browser use", "cdp", "automation", "agent"}):
        signals.append("Agent、浏览器自动化或工具调用相关")
    if _has_any(text, {"paper", "arxiv", "research", "evaluation", "benchmark"}):
        signals.append("论文、评测或研究信号")
    if _has_any(text, {"safety", "policy", "security", "authorization", "risk"}):
        signals.append("安全、政策或风险边界变化")
    if _has_any(text, {"github", "open source", "repository"}):
        signals.append("有开源或仓库线索，适合进一步验证")
    return _dedupe_keep_order(signals)


def _why_it_matters(item: RadarItem, language: str) -> str:
    strengths: list[str] = []
    if item.world_value >= 7:
        strengths.append("AI 世界影响较大" if language == "zh" else "broad AI-world impact")
    if item.learning_value >= 6.5:
        strengths.append("学习价值明确" if language == "zh" else "clear learning value")
    if item.practice_value >= 6.5:
        strengths.append("适合动手实践" if language == "zh" else "hands-on practice potential")
    if item.current_focus_fit >= 5 or item.related_focus_topics:
        strengths.append("贴合当前焦点" if language == "zh" else "current-focus relevance")
    if not strengths:
        strengths.append("信号价值中等" if language == "zh" else "moderate signal value")
    if language == "zh":
        return "主要信号：" + "、".join(strengths) + "。"
    return "Signals: " + ", ".join(strengths) + "."


def _uncertainty(item: RadarItem, language: str) -> str:
    if item.confidence == "high":
        return "低；但采取行动前仍应打开原始链接确认版本号、发布日期和适用范围。" if language == "zh" else "Low, but still check the linked source for version, date, and scope."
    if item.confidence == "medium":
        return "中；重要结论需要回到一手来源再确认。" if language == "zh" else "Medium; verify important claims against a primary source."
    return "高；在原始来源支撑前，只能当作线索。" if language == "zh" else "High; treat this as a lead until an original source supports it."


def _item_action(item: RadarItem, language: str) -> str:
    text = item.text_for_matching
    if language == "zh":
        if item.action_type == "verify" or "needs_verification" in item.labels:
            return "先找到原始来源，再放入正式雷达判断。"
        if item.action_type == "try" or "worth_trying" in item.labels:
            return "转成一个小实验，优先验证安装、API 或仓库可复现性。"
        if item.action_type == "study" or "worth_learning" in item.labels:
            return "加入学习队列，提取一个关键概念或机制。"
        if "mcp" in text:
            return "把更新点映射到 MCP 学习笔记：协议能力、工具 schema、错误语义、传输层四类里。"
        if "browser use" in text:
            return "用一个固定网页任务试跑：打开页面、读取状态、点击/输入、截图，并记录延迟和稳定性。"
        return "继续观察，等待更强后续信号。"

    if item.action_type == "verify" or "needs_verification" in item.labels:
        return "Find the original source before using it in the radar."
    if item.action_type == "try" or "worth_trying" in item.labels:
        return "Turn this into a small experiment or repo/API trial."
    if item.action_type == "study" or "worth_learning" in item.labels:
        return "Add this to the learning queue and extract the key concept."
    if "mcp" in text:
        return "Map the update to MCP notes: protocol capabilities, tool schema, errors, or transport."
    if "browser use" in text:
        return "Run a fixed browser task and record state quality, clicks, inputs, screenshots, latency, and stability."
    return "Monitor for a stronger follow-up signal."


def _actions_for(items: list[RadarItem], language: str) -> list[str]:
    actions: list[str] = []
    for item in items[:8]:
        title = _display_title(item)
        if language == "zh":
            if item.action_type == "verify":
                action = f"核验一手来源：{title}（{_item_date(item)}）"
            elif item.action_type == "try":
                action = f"动手试验：{title} - {_item_action(item, 'zh')}"
            elif item.action_type == "study":
                action = f"学习拆解：{title} - {_item_action(item, 'zh')}"
            elif item.action_type == "read":
                action = f"重点阅读：{title}（{_coverage_label(item, 'zh')}）"
            else:
                continue
        else:
            if item.action_type == "verify":
                action = f"Verify primary source for: {title} ({_item_date(item)})"
            elif item.action_type == "try":
                action = f"Try hands-on: {title} - {_item_action(item, 'en')}"
            elif item.action_type == "study":
                action = f"Study: {title} - {_item_action(item, 'en')}"
            elif item.action_type == "read":
                action = f"Read closely: {title} ({_coverage_label(item, 'en')})"
            else:
                continue
        actions.append(action)
        if len(actions) >= 6:
            break
    return actions


def _related_lines(item: RadarItem, language: str) -> list[str]:
    if not item.related_items:
        return []
    related = item.related_items[:3]
    if language == "zh":
        details = "；".join(f"{_display_title(related_item)}（{_item_date(related_item)}）" for related_item in related)
        return [f"- 相关更新：{details}"]
    details = "; ".join(f"{_display_title(related_item)} ({_item_date(related_item)})" for related_item in related)
    return [f"- Related updates: {details}"]


def _coverage_label(item: RadarItem, language: str) -> str:
    if language == "zh":
        return COVERAGE_ZH.get(item.coverage_area, item.coverage_area or "未知")
    return item.coverage_area.replace("_", " ") if item.coverage_area else "unknown"


def _source_role_label(item: RadarItem, language: str) -> str:
    if language == "zh":
        return SOURCE_ROLE_ZH.get(item.source_role, item.source_role or "未知")
    return item.source_role.replace("_", " ") if item.source_role else "unknown"


def _action_label(item: RadarItem, language: str) -> str:
    if language == "zh":
        return ACTION_ZH.get(item.action_type, item.action_type or "观察")
    return item.action_type or "monitor"


def _recommendation_reason(item: RadarItem, language: str) -> str:
    if language != "zh":
        return item.recommendation_reason or "No recommendation reason generated."
    if not item.recommendation_reason:
        return "暂无推荐理由。"
    parts = [
        REASON_ZH.get(part.strip(), part.strip())
        for part in item.recommendation_reason.split(";")
        if part.strip()
    ]
    return "；".join(parts) + "。"


def _format_labels(labels: list[str], language: str) -> str:
    if not labels:
        return "无" if language == "zh" else "none"
    if language == "zh":
        return "、".join(LABELS_ZH.get(label, label) for label in labels)
    return ", ".join(labels)


def _display_title(item: RadarItem) -> str:
    title = item.title.strip()
    lowered = title.lower()
    if lowered.startswith("v") and any(char.isdigit() for char in lowered[:5]):
        return f"{item.source_name}: {title}"
    if title[:1].isdigit() and "." in title[:8]:
        return f"{item.source_name}: {title}"
    if title.startswith("@"):
        return f"{item.source_name}: {title}"
    return title


def _run_report_date(run: RadarRun) -> str:
    if run.report_date:
        return run.report_date
    return _format_date(run.generated_at, to_report_timezone=True)


def _item_date(item: RadarItem, use_fetched: bool = False) -> str:
    raw = item.fetched_time if use_fetched else item.published_time
    if not raw:
        return "未知"
    return _format_date(raw, to_report_timezone=use_fetched)


def _format_date(value: str, to_report_timezone: bool = False) -> str:
    raw = value.strip()
    if not raw:
        return "未知"
    parsed = _parse_date(raw)
    if parsed is None:
        return raw
    if to_report_timezone:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(REPORT_TZ)
    return parsed.date().isoformat()


def _format_datetime_for_report(value: str) -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(REPORT_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def _parse_date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _shorten(text: str, max_chars: int = 520) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    cutoff = compact[: max_chars + 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return cutoff + "..."


def _has_any(text: str, keywords: set[str]) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None
