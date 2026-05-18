from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from .models import RadarItem, RadarRun

REPORT_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


SECTION_RULES = {
    "Models And Capabilities": {"model", "models", "capabilities", "multimodal", "reasoning"},
    "Tools And Products": {"tools", "products", "api", "sdk", "developer_tools"},
    "Open Source And Developer Ecosystem": {"open_source", "open source", "github", "developer_tools"},
    "Papers And Concepts": {"papers", "paper", "research", "concept", "dataset", "evals", "benchmarks"},
    "Industry And Trends": {"industry", "policy", "adoption", "business", "trend", "trends"},
}

ZH_SECTIONS = {
    "Models And Capabilities": "模型与能力",
    "Tools And Products": "工具与产品",
    "Open Source And Developer Ecosystem": "开源与开发者生态",
    "Papers And Concepts": "论文与概念",
    "Industry And Trends": "行业与趋势",
}

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


def render_daily_radar(run: RadarRun, language: str = "zh") -> str:
    if language == "zh":
        return _render_daily_radar_zh(run)
    return _render_daily_radar_en(run)


def _render_daily_radar_zh(run: RadarRun) -> str:
    lines: list[str] = [
        "# AI 每日雷达",
        "",
        f"生成时间：{_format_datetime_for_report(run.generated_at)}",
        "",
    ]
    if run.fetch_errors:
        lines.extend(["## 抓取备注", ""])
        for error in run.fetch_errors:
            lines.append(f"- {error}")
        lines.append("")

    top_items = run.items[:3]
    used_ids = set()
    lines.extend(["## 必须关注", ""])
    if top_items:
        for item in top_items:
            used_ids.add(item.id)
            lines.extend(_format_item(item, language="zh"))
    else:
        lines.append("- 暂无采集结果。")
    lines.append("")

    for section, keywords in SECTION_RULES.items():
        section_items = [
            item
            for item in run.items
            if item.id not in used_ids and _matches_section(item, section, keywords)
        ][:4]
        for item in section_items:
            used_ids.add(item.id)
        lines.extend([f"## {ZH_SECTIONS[section]}", ""])
        if section_items:
            for item in section_items:
                lines.extend(_format_item(item, language="zh"))
        else:
            lines.append("- 本区暂未筛出高信号条目。")
        lines.append("")

    focus_items = [
        item
        for item in run.items
        if item.current_focus_fit >= 4.0 or item.related_focus_topics
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
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- 暂无行动候选。")
    lines.append("")
    return "\n".join(lines)


def _render_daily_radar_en(run: RadarRun) -> str:
    lines: list[str] = [
        "# AI Daily Radar",
        "",
        f"Generated: {_format_datetime_for_report(run.generated_at)}",
        "",
    ]
    if run.fetch_errors:
        lines.extend(["## Fetch Notes", ""])
        for error in run.fetch_errors:
            lines.append(f"- {error}")
        lines.append("")

    top_items = run.items[:3]
    used_ids = set()
    lines.extend(["## Must Know", ""])
    if top_items:
        for item in top_items:
            used_ids.add(item.id)
            lines.extend(_format_item(item, language="en"))
    else:
        lines.append("- No items collected.")
    lines.append("")

    for section, keywords in SECTION_RULES.items():
        section_items = [
            item
            for item in run.items
            if item.id not in used_ids and _matches_section(item, section, keywords)
        ][:4]
        for item in section_items:
            used_ids.add(item.id)
        lines.extend([f"## {section}", ""])
        if section_items:
            for item in section_items:
                lines.extend(_format_item(item, language="en"))
        else:
            lines.append("- No high-signal items in this section.")
        lines.append("")

    focus_items = [
        item
        for item in run.items
        if item.current_focus_fit >= 4.0 or item.related_focus_topics
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
    if actions:
        lines.extend(f"- {action}" for action in actions)
    else:
        lines.append("- No action candidates.")
    lines.append("")
    return "\n".join(lines)


def _format_item(item: RadarItem, language: str) -> list[str]:
    labels = _format_labels(item.labels, language)
    source = f"[{item.source_name}]({item.url})" if item.url else item.source_name
    evidence = _shorten(
        item.claims[0] if item.claims else item.summary or "Collected source signal.",
        max_chars=360,
    )
    interpretation = _interpretation(item, language)
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
            f"- 中文要点：{_summary_zh(item)}",
            f"- 原文证据：{evidence}",
            f"- 为什么重要：{interpretation}",
            f"- 不确定性：{uncertainty}",
            f"- 建议行动：{action}",
        ]
        lines.extend(_related_lines(item, language="zh"))
        lines.append("")
        return lines
    lines = [
        f"### {_display_title(item)}",
        "",
        f"- Source: {source}",
        f"- Date: published/updated {_item_date(item)}; fetched {_item_date(item, use_fetched=True)}",
        f"- Trust: {item.source_tier} | confidence: {item.confidence} | score: {item.final_score:.1f}/10 | labels: {labels}",
        f"- Fact: {evidence}",
        f"- Why it matters: {interpretation}",
        f"- Uncertainty: {uncertainty}",
        f"- Action: {action}",
    ]
    lines.extend(_related_lines(item, language="en"))
    lines.append("")
    return lines


def _related_lines(item: RadarItem, language: str) -> list[str]:
    if not item.related_items:
        return []
    related = item.related_items[:3]
    if language == "zh":
        details = "；".join(
            f"{_display_title(related_item)}（{_item_date(related_item)}，{_related_hint_zh(related_item)}）"
            for related_item in related
        )
        suffix = "" if len(item.related_items) <= 3 else f"；另有 {len(item.related_items) - 3} 条"
        return [f"- 相关更新：{details}{suffix}"]
    details = "; ".join(
        f"{_display_title(related_item)} ({_item_date(related_item)}, {related_item.final_score:.1f}/10)"
        for related_item in related
    )
    suffix = "" if len(item.related_items) <= 3 else f"; plus {len(item.related_items) - 3} more"
    return [f"- Related updates: {details}{suffix}"]


def _related_hint_zh(item: RadarItem) -> str:
    signals = _summary_signals_zh(item)
    if signals:
        return signals[0]
    if item.labels:
        return _format_labels(item.labels[:1], language="zh")
    return f"{item.final_score:.1f}/10"


def _summary_zh(item: RadarItem) -> str:
    title = item.title.lower()
    text = item.text_for_matching
    source = item.source_name

    if "agentstop" in title:
        return "这篇论文把本地 LLM agent 的时间、token、能耗和失败重试当成可测问题，并提出提前终止低成功率轨迹的监督器。"
    if "learning to internalize self-critique" in title or "icrl" in title:
        return "这篇论文研究如何让 agent 把外部批评内化成自身能力，用强化学习联合训练 solver 和 critic，减少对批评提示的依赖。"
    if "verifiable agentic infrastructure" in title:
        return "这篇论文讨论 autonomous agents 在云和企业系统中带来的授权风险，核心问题是：凭证有效不代表 agent 动作语义安全。"
    if "cax-agent" in title:
        return "这篇论文把 agent harness 用到工程仿真自动化，重点是用工具封装、状态管理和故障恢复提升领域 agent 的可靠性。"
    if "quantization undoes alignment" in title:
        return "这篇论文关注量化压缩后 LLM 对齐和偏见指标可能退化的问题，适合放进模型部署与评测风险清单。"
    if "teamtr" in title or "multi-agent llm coordination" in title:
        return "这篇论文讨论多 agent 协作微调中的分布漂移问题，重点是多 agent 系统为什么可能弱于单模型基线。"
    if "capability conditioned scaffolding" in title:
        return "这篇论文关注人类与 LLM 协作时如何按模型能力动态搭脚手架，适合跟踪专业工作流里的 agent 辅助设计。"
    if "sea's view" in title or "codex" in title and "sea" in source.lower():
        return "这是 OpenAI 关于 Sea 部署 Codex 的案例，重点不是模型发布，而是 Codex 在工程团队中的组织级采用信号。"

    if source == "OpenAI Agents Python Releases":
        return _release_summary_zh(
            item,
            product="OpenAI Agents Python SDK",
            fallback="这是 OpenAI Agents Python SDK 的版本更新，重点关注 agent 运行、工具调用、会话、sandbox 和 realtime 行为变化。",
        )
    if source == "OpenAI Python SDK Releases":
        return _release_summary_zh(
            item,
            product="OpenAI Python SDK",
            fallback="这是 OpenAI Python SDK 的版本更新，重点关注 API 兼容性、枚举变更和客户端行为变化。",
        )
    if source == "Anthropic Python SDK Releases":
        return _release_summary_zh(
            item,
            product="Anthropic Python SDK",
            fallback="这是 Anthropic Python SDK 的版本更新，重点关注 API 客户端兼容性和开发者集成影响。",
        )
    if source == "Browser Use Releases":
        if "cli" in text:
            return "这是 Browser Use 的 CLI 方向更新，重点是让编码 agent 直接通过命令行控制浏览器、读取 DOM 状态并执行点击/输入/截图。"
        return _release_summary_zh(
            item,
            product="Browser Use",
            fallback="这是 Browser Use 的版本更新，重点关注浏览器自动化稳定性、CDP 连接、页面状态读取和 agent 可用性。",
        )
    if source.startswith("MCP "):
        return _release_summary_zh(
            item,
            product=source,
            fallback="这是 MCP SDK 的版本更新，重点关注工具协议、schema、错误语义、传输层和兼容性变化。",
        )
    if source.startswith("arXiv"):
        return _paper_summary_zh(item)

    signals = _summary_signals_zh(item)
    if signals:
        return f"这条来自 {source}，主要信息是：" + "；".join(signals) + "。"
    return f"这条来自 {source}，需要结合原文判断它是否代表真实变化，而不是只看标题。"


def _release_summary_zh(item: RadarItem, product: str, fallback: str) -> str:
    signals = _summary_signals_zh(item)
    if not signals:
        return fallback
    return f"{product} 的 {_display_title(item).split(': ', 1)[-1]} 更新，主要涉及：" + "；".join(signals[:3]) + "。"


def _paper_summary_zh(item: RadarItem) -> str:
    signals = _summary_signals_zh(item)
    if signals:
        return "这篇论文主要讨论：" + "；".join(signals[:3]) + "。"
    return "这是一篇来自 arXiv 的论文条目，优先看 abstract、方法、实验设置和是否有代码，再决定是否进入学习地图。"


def _summary_signals_zh(item: RadarItem) -> list[str]:
    text = item.text_for_matching
    signals: list[str] = []
    if "default model" in text or "gpt-" in text:
        signals.append("默认模型或模型参数变化，可能影响未显式配置的 agent 行为")
    if "sandbox" in text:
        signals.append("sandbox、本地文件或执行边界变化")
    if "mcp" in text:
        signals.append("MCP 工具接入、schema、命名或错误处理变化")
    if "realtime" in text:
        signals.append("realtime agent/session 行为变化")
    if "concurrency" in text or "parallel" in text:
        signals.append("工具并发、调度或运行效率变化")
    if "oauth" in text or "authorization" in text or "security" in text or "cve" in text:
        signals.append("安全、授权或身份边界变化")
    if "browser use" in text or "cdp" in text or "chrome devtools protocol" in text:
        signals.append("浏览器自动化、CDP 或 DOM 状态读取能力变化")
    if "energy" in text or "battery" in text or "token" in text:
        signals.append("agent 运行成本、能耗或 token 浪费问题")
    if "benchmark" in text or "evaluation" in text or "eval" in text:
        signals.append("评测方法或 benchmark 信号")
    if "code is available" in text or "github.com" in text:
        signals.append("有代码或仓库线索，具备复现实验可能")
    if "bias" in text or "alignment" in text or "quantization" in text:
        signals.append("模型压缩、偏见或对齐风险")
    if "multi-agent" in text:
        signals.append("多 agent 协作、训练或可靠性问题")
    if "self-critique" in text or _has_word(text, "critic"):
        signals.append("agent 自我批评或自我改进机制")
    return _dedupe_keep_order(signals)


def _matches_section(item: RadarItem, section: str, keywords: set[str]) -> bool:
    text = _section_text(item)
    values = {value.lower().replace("_", " ") for value in [item.raw_category] if value}

    if any(keyword.lower().replace("_", " ") in values for keyword in keywords):
        return True
    if section == "Models And Capabilities":
        return any(term in text for term in ["model", "multimodal", "reasoning", "benchmark", "quantization", "alignment"])
    if section == "Tools And Products":
        return any(term in text for term in ["sdk", "api", "cli", "codex", "product", "release", "tool"])
    if section == "Open Source And Developer Ecosystem":
        return any(term in text for term in ["github", "open source", "repository", "mcp", "developer"])
    if section == "Papers And Concepts":
        return item.source_name.lower().startswith("arxiv") or any(term in text for term in ["paper", "abstract", "method", "dataset", "evaluation"])
    if section == "Industry And Trends":
        return any(term in text for term in ["company", "team", "enterprise", "adoption", "business", "industry"])
    return False


def _section_text(item: RadarItem) -> str:
    return " ".join(
        part
        for part in [
            item.title,
            item.summary,
            " ".join(item.claims),
            item.raw_category,
        ]
        if part
    ).lower().replace("_", " ")


def _interpretation(item: RadarItem, language: str) -> str:
    if language != "zh":
        return _interpretation_en(item)

    reasons = _specific_reasons(item)
    if reasons:
        return "；".join(reasons) + "。"
    return _fallback_interpretation(item, language="zh")


def _interpretation_en(item: RadarItem) -> str:
    reasons = _specific_reasons_en(item)
    if reasons:
        return "; ".join(reasons) + "."
    return _fallback_interpretation(item, language="en")


def _specific_reasons(item: RadarItem) -> list[str]:
    text = item.text_for_matching
    title = item.title.lower()
    reasons: list[str] = []

    if "browser use" in text and "cli" in text:
        reasons.append("它直接影响当前 Browser Use 学习主线，重点不是新闻，而是可立刻验证的 CLI/浏览器控制能力")
    if "cdp" in text or "chrome devtools protocol" in text:
        reasons.append("它从 Playwright/选择器思路转向 CDP/DOM 状态读取，值得比较延迟、稳定性和 token 成本")
    if "codex" in text or "claude code" in text:
        reasons.append("它明确面向 CLI coding agents，可放进你的 Codex/Claude Code 工作流做实测")
    if "mcp" in text:
        reasons.append("它涉及 MCP 工具协议或 SDK 变化，可能影响 agent 工具接入、命名、错误处理或兼容性")
    if "sandbox" in text:
        reasons.append("它触及 sandbox 边界和本地文件访问规则，和安全运行 agent 直接相关")
    if "default model" in text or "gpt-" in text:
        reasons.append("它改变默认模型或模型配置，可能让未显式指定模型的 agent 行为发生漂移")
    if "realtime" in text:
        reasons.append("它涉及 realtime agent/session 行为，适合跟踪语音、多模态或低延迟 agent 能力")
    if "concurrency" in text or "parallel" in text:
        reasons.append("它涉及工具并发或调度，能影响 agent 运行速度、成本和失败模式")
    if "security" in text or "cve" in text or "authorization" in text:
        reasons.append("它是安全/授权相关信号，优先级高于普通功能更新")
    if "breaking" in text or "major changes" in text or "alpha" in title:
        reasons.append("它包含破坏性或大版本变化，适合提前评估迁移成本")
    if "code is available" in text or "github.com" in text:
        reasons.append("它提供代码或仓库线索，不止能读，还可以转成可复现实验")
    if "agentstop" in title or "energy" in text or "battery" in text:
        reasons.append("它把本地 agent 的能耗、失败重试和提前终止做成可测问题，适合形成实验任务")
    if "self-critique" in text or _has_word(text, "critic"):
        reasons.append("它关注 agent 自我批评/自我改进机制，适合补足 agent 可靠性学习路线")
    if "evaluation" in text or "benchmark" in text or "eval" in text:
        reasons.append("它提供评测或 benchmark 视角，可以帮助你把学习从功能试用推进到可比较的判断")
    if item.source_name.lower().startswith("arxiv"):
        reasons.append("它来自论文源，需要关注方法、数据、代码可复现性，而不是只看标题热度")

    return _dedupe_keep_order(reasons)[:3]


def _specific_reasons_en(item: RadarItem) -> list[str]:
    text = item.text_for_matching
    reasons: list[str] = []
    if "browser use" in text and "cli" in text:
        reasons.append("directly affects the Browser Use focus and can be tested as a CLI workflow")
    if "mcp" in text:
        reasons.append("touches MCP tool integration, naming, error handling, or compatibility")
    if "sandbox" in text:
        reasons.append("changes sandbox boundaries or local file access behavior")
    if "default model" in text or "gpt-" in text:
        reasons.append("may change agent behavior when model settings are implicit")
    if "security" in text or "cve" in text or "authorization" in text:
        reasons.append("is a safety/security signal rather than a routine feature update")
    if "code is available" in text or "github.com" in text:
        reasons.append("has code or repository evidence that can become a reproducible experiment")
    if item.source_name.lower().startswith("arxiv"):
        reasons.append("comes from a paper source, so methods and reproducibility matter more than title heat")
    return _dedupe_keep_order(reasons)[:3]


def _fallback_interpretation(item: RadarItem, language: str) -> str:
    strengths: list[str] = []
    if item.world_value >= 7:
        strengths.append("AI 世界影响较大" if language == "zh" else "broad AI-world impact")
    if item.learning_value >= 7:
        strengths.append("学习价值明确" if language == "zh" else "clear learning value")
    if item.practice_value >= 7:
        strengths.append("适合动手实践" if language == "zh" else "hands-on practice potential")
    if item.current_focus_fit >= 5:
        strengths.append("贴合当前焦点" if language == "zh" else "current-focus relevance")
    if not strengths:
        strengths.append("信号价值中等" if language == "zh" else "moderate signal value")
    if language == "zh":
        return "主要信号：" + "、".join(strengths) + "。"
    return "Signals: " + ", ".join(strengths) + "."


def _uncertainty(item: RadarItem, language: str) -> str:
    if item.confidence == "high":
        if language == "zh":
            return "低；但采取行动前仍应打开原始链接确认版本号、发布日期和适用范围。"
        return "Low, but still check the linked source for version, date, and scope."
    if item.confidence == "medium":
        if language == "zh":
            return "中；重要结论需要回到一手来源再确认。"
        return "Medium; verify important claims against a primary source."
    if language == "zh":
        return "高；在原始来源支撑前，只能当作线索。"
    return "High; treat this as a lead until an original source supports it."


def _item_action(item: RadarItem, language: str) -> str:
    if language != "zh":
        return _item_action_en(item)

    text = item.text_for_matching
    title = item.title.lower()
    if "browser use" in text and "cli" in text:
        return "用一个固定网页任务试跑 CLI：打开页面、读取 state、点击/输入、截图，并记录延迟和 token 体感。"
    if "agentstop" in title:
        return "读论文方法部分，记录它用哪些信号预测失败；若代码可用，先跑一个最小 benchmark。"
    if "default model" in text:
        return "检查你自己的 agents 配置里是否依赖默认模型；必要时显式 pin model 后做一次行为对比。"
    if "sandbox" in text:
        return "重点读 sandbox 迁移说明，用一个本地文件访问案例验证新边界是否会影响现有工作流。"
    if "mcp" in text and ("breaking" in text or "major changes" in text or "alpha" in title):
        return "挑一个最小 MCP server/client，验证工具命名、错误处理和 schema 兼容性。"
    if "mcp" in text:
        return "把更新点映射到你的 MCP 学习笔记：协议能力、工具 schema、错误语义、传输层四类里。"
    if item.source_name.lower().startswith("arxiv"):
        return "先读 abstract 和方法图，再判断是否进入本周学习地图；有代码则优先复现一个最小例子。"
    if "worth_trying" in item.labels:
        return "转成一个小实验，优先验证安装、API 或仓库可复现性。"
    if "worth_learning" in item.labels:
        return "加入学习队列，提取一个关键概念或机制。"
    if "needs_verification" in item.labels:
        return "先找到原始来源，再放入正式雷达判断。"
    return "继续观察，等待更强后续信号。"


def _item_action_en(item: RadarItem) -> str:
    text = item.text_for_matching
    title = item.title.lower()
    if "browser use" in text and "cli" in text:
        return "Run a fixed browser task with the CLI and record latency, state quality, clicks, inputs, and screenshots."
    if "agentstop" in title:
        return "Read the method section and run the smallest available benchmark if code is linked."
    if "default model" in text:
        return "Check whether your agents depend on implicit default models; pin one model and compare behavior."
    if "sandbox" in text:
        return "Read the migration note and test one local-file sandbox boundary case."
    if "mcp" in text:
        return "Map the update to MCP notes: protocol capabilities, tool schema, errors, or transport."
    if item.source_name.lower().startswith("arxiv"):
        return "Read abstract and method first; reproduce a minimal example if code is available."
    if "worth_trying" in item.labels:
        return "Turn this into a small experiment or repo/API trial."
    if "worth_learning" in item.labels:
        return "Add this to the learning queue and extract the key concept."
    if "needs_verification" in item.labels:
        return "Find the original source before using it in the radar."
    return "Monitor for a stronger follow-up signal."


def _actions_for(items: list[RadarItem], language: str) -> list[str]:
    actions: list[str] = []
    for item in items[:8]:
        if language == "zh":
            if "needs_verification" in item.labels:
                action = f"核验一手来源：{_display_title(item)}（{_item_date(item)}）"
            elif "worth_trying" in item.labels:
                action = f"动手试验：{_display_title(item)} - {_item_action(item, language='zh')}"
            elif "worth_learning" in item.labels:
                action = f"学习拆解：{_display_title(item)} - {_item_action(item, language='zh')}"
            else:
                continue
        else:
            if "needs_verification" in item.labels:
                action = f"Verify primary source for: {_display_title(item)} ({_item_date(item)})"
            elif "worth_trying" in item.labels:
                action = f"Try hands-on: {_display_title(item)} - {_item_action(item, language='en')}"
            elif "worth_learning" in item.labels:
                action = f"Study: {_display_title(item)} - {_item_action(item, language='en')}"
            else:
                continue
        actions.append(action)
        if len(actions) >= 6:
            break
    return actions


def _format_labels(labels: list[str], language: str) -> str:
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
    local = parsed.astimezone(REPORT_TZ)
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")


def _parse_date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _shorten(text: str, max_chars: int = 520) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    cutoff = compact[: max_chars + 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return cutoff + "..."


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
