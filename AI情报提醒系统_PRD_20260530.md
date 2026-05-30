# AI 情报提醒系统 PRD

Status: ready-for-agent

Created: 2026-05-30

## Problem Statement

用户希望持续了解 AI 领域，尤其是主流模型厂商、AI 编程工具、Agent 工作流、官方工程博客、API 变化、价格变化和重大开源动态，但不希望每天主动打开网页、翻信息流、刷短视频或依赖营销号筛选信息。

当前痛点不是“信息不够”，而是信息太多、来源混杂、主动获取成本高。用户需要一个常驻在 Mac mini 上的轻量后台系统，持续获取可靠信息源的新内容，并只在真正重要时通过飞书提醒。普通内容进入每天早上的摘要，不打断用户。

系统的目标是做“AI 信息门卫”，不是做新闻门户、研究平台、社交媒体监控平台或全文知识库。

## Solution

构建一个轻量本地版 AI 情报提醒系统，部署在 Mac mini 上，通过定时任务每 10 分钟抓取信息源，提取有意义的新内容，去重、归并、按规则判断重要性，并在命中强提醒规则时发送飞书消息。每天早上生成并发送日报，同时在本地保存 Markdown 留档。

第一版不接 LLM。重要性判断采用规则优先、来源分权、内容类型分层的方式。官方源和原始仓库是事实依据，AI HOT 和 agents-radar 这类聚合源只作为补漏雷达和候选来源，不能单独决定重大提醒。

第一版使用本地配置文件维护 curated source manifest，用 SQLite 记录已抓取条目、事件、提醒历史和状态。系统提供 CLI 用于轮询、生成日报、测试规则、重分类，以及标记已读、稍后看和忽略。

## User Stories

1. As a user, I want the system to continuously monitor AI information sources, so that I do not need to manually open multiple websites every day.
2. As a user, I want only highly important AI updates to interrupt me, so that I am not overwhelmed by low-value notifications.
3. As a user, I want normal AI updates to appear in a morning digest, so that I can catch up without constant interruptions.
4. As a user, I want official sources to have higher authority than aggregators, so that alerts are based on primary information.
5. As a user, I want AI HOT to be used as a discovery source, so that it can help surface Chinese summaries and community signals without becoming the final source of truth.
6. As a user, I want agents-radar to be used as a supplementary aggregator, so that the system has broader coverage of AI ecosystem updates.
7. As a user, I want Anthropic Engineering to be monitored directly, so that Claude Code, MCP, Agent Skills, managed agents, and agent workflow updates are not missed.
8. As a user, I want Anthropic News, Research, developer release notes, Claude Code changelog, desktop changelog, GitHub changelog, and status pages to be monitored, so that Anthropic-related updates are covered across product, engineering, research, tooling, and incidents.
9. As a user, I want OpenAI official news, status, docs changelog, pricing, model, and GitHub-related sources to be monitored, so that changes affecting API usage and AI development workflows are detected.
10. As a user, I want Qwen, DeepSeek, Mistral, and Google DeepMind official sources to be monitored, so that major model ecosystem changes are not missed.
11. As a user, I want AI programming and Agent workflow sources to be prioritized, so that Codex, Claude Code, Cursor, OpenCode, MCP, Agents SDK, GitHub Copilot, and related tools are watched closely.
12. As a user, I want pricing pages to be monitored for substantive changes, so that I know when costs or billing assumptions change.
13. As a user, I want model list pages to be monitored for new models, removed models, deprecated models, context length changes, or capability changes, so that I can adjust my workflows.
14. As a user, I want deprecation and migration notices to trigger strong alerts, so that I do not miss breaking changes.
15. As a user, I want status incidents to trigger strong alerts, so that I know when model services or developer platforms are down or degraded.
16. As a user, I want the system to ignore page styling, scripts, image metadata, recommendation blocks, and other non-content changes, so that notifications stay clean.
17. As a user, I want the system to detect only new content or substantive content changes, so that every stored item represents something worth evaluating.
18. As a user, I want duplicate reports of the same event to be merged, so that I receive one alert instead of repeated alerts from multiple sources.
19. As a user, I want later mentions of an already-alerted event to be added to the existing event, so that the digest can show supporting sources without interrupting me again.
20. As a user, I want the system to keep a cooldown window for similar events, so that noisy repeated coverage does not create repeated alerts.
21. As a user, I want alert messages to include title, source, why it matters, and original link, so that I can quickly decide whether to open the source.
22. As a user, I want the system to keep original links instead of storing full article text, so that the local system remains lightweight and respects source ownership.
23. As a user, I want every item to have a status such as new, alerted, in daily, read, saved, or ignored, so that I can manage what I have already seen.
24. As a user, I want to mark items as read, saved, or ignored from the CLI, so that I can keep the workflow simple without building a full web interface.
25. As a user, I want saved items to appear separately in the digest, so that I can return to things I intentionally kept for later.
26. As a user, I want a morning digest sent to Feishu, so that I get a concise daily briefing at the start of the day.
27. As a user, I want the morning digest saved locally as Markdown, so that there is a searchable archive of daily AI intelligence.
28. As a user, I want the digest to show already-alerted items, worth-reading items, source failures, and filtering statistics, so that I can understand what happened without opening logs.
29. As a user, I want failed sources to be reported in the digest, so that I know when coverage may be incomplete.
30. As a user, I want the system to run on Mac mini, so that it can stay online without depending on my primary Mac.
31. As a user, I want Feishu to be the first notification channel, so that both phone and desktop can receive alerts through one stable channel.
32. As a user, I want the system to use a dedicated Feishu group with a custom bot, so that AI intelligence alerts do not pollute work groups.
33. As a user, I want secrets such as Feishu webhook URLs to live outside normal config, so that I can safely share source and rule configuration for review.
34. As a user, I want the source manifest to be curated manually, so that only trusted sources are allowed into the system.
35. As a user, I want automatic source health checks, so that broken sources, stale feeds, or changed page structures are visible.
36. As a user, I want new sources to require manual approval, so that the system does not slowly become a noisy crawler.
37. As a user, I want rules to be configurable without code changes, so that I can adjust priorities and keywords as my interests change.
38. As a user, I want to test alert rules against the last 24 hours of data, so that I can tune the system before trusting it.
39. As a user, I want to reclassify recent items after changing rules, so that the historical state reflects improved rules without resending old alerts.
40. As a user, I want the first version not to depend on LLM APIs, so that it remains reliable, cheap, and simple to operate.
41. As a user, I want LLM summarization to remain a future enhancement, so that the first version does not block on provider keys or model behavior.
42. As a user, I want code to be version controlled while local data, logs, reports, config, and secrets stay uncommitted, so that the tool can evolve safely.
43. As a user, I want no first-version web UI, so that the implementation focuses on background operation, CLI, Feishu notifications, and Markdown reports.
44. As a user, I want the system to be easy for a coding agent to implement and test, so that future changes can be made safely.

## Implementation Decisions

- The first version will be a lightweight local system deployed on Mac mini.
- The runtime model will be scheduled command execution, not a long-running web service.
- The scheduler will run polling every 10 minutes and daily digest generation every morning.
- The first notification channel will be Feishu via a dedicated group and custom bot webhook.
- The system will not use WeChat, email, Feishu app OAuth, or a custom web dashboard in the first version.
- The system will not use LLM APIs in the first version.
- The system will treat official sources, official GitHub repositories, official status pages, curated aggregators, media, and social sources as different authority levels.
- Official sources can trigger direct alerts when strong rules match.
- Official GitHub releases and changelogs can trigger direct alerts when strong rules match.
- Official status pages can trigger direct alerts for incidents, outages, degradations, and recovery events.
- Curated aggregators can create candidates and supplement events, but should not be the sole authority for a strong alert unless the linked target is official or an original GitHub source.
- Media and social sources are out of the direct-alert path in the first version and should only appear in daily summaries if later added.
- The source manifest will be manually curated and configuration-driven.
- Source manifest entries should include source name, vendor, source type, authority level, URL, priority, and parsing strategy.
- Vendors should be modeled by source categories rather than a single company URL.
- Source categories should include news, engineering, research, developer changelog, status, pricing, model list, deprecation notices, GitHub release, and aggregator.
- Anthropic coverage must include engineering content, not only news.
- The content extraction layer should normalize sources into stable items with title, URL, source, vendor, published time if available, detected time, content type, fingerprint, and raw metadata needed for traceability.
- The system should compare meaningful fields, not full web page HTML.
- RSS and Atom sources should be deduplicated by stable feed identifiers, canonical links, titles, and timestamps.
- GitHub releases should be deduplicated by repository and release or tag.
- GitHub changelog files should be fingerprinted and parsed by newly added version sections where feasible.
- News, engineering, and research list pages should extract article links, titles, dates, and summaries where available.
- Pricing, model, and deprecation pages should use normalized content fingerprints scoped to the meaningful content area.
- Status pages should prefer structured status APIs or feeds where available.
- Deduplication should have both hard and approximate modes.
- Hard deduplication should cover identical URL, canonical URL, identical feed ID, identical GitHub release tag, and identical source item ID.
- Approximate deduplication should cover normalized title similarity, same vendor plus same strong keyword in a cooldown window, and aggregator links pointing to the same official source.
- Event grouping should merge multiple source items into one event.
- Alerts should be sent once per event during the cooldown window.
- Later supporting sources should update the existing event rather than triggering a fresh alert.
- The first version should use SQLite for items, events, alert history, source health, rule classification, and item state.
- The first version should not store full article text.
- Stored records should include the data required to determine newness, dedupe, classify importance, generate alerts, generate daily reports, and provide traceability back to the original source.
- Item states should include new, alerted, in daily, read, saved, and ignored.
- Alert importance should be derived from source authority, content type, keyword rules, and event context.
- Strong alert rules should include official model releases, API changes, pricing changes, rate-limit changes, deprecations, migrations, major developer tool updates, security issues, outages, and status incidents.
- The initial high-interest keywords should include Codex, Claude Code, MCP, Agents SDK, Cursor, OpenCode, GitHub Copilot, model, API, pricing, rate limit, deprecation, security, outage, release, new model, Qwen, DeepSeek, OpenAI, Anthropic, and similar variants.
- Alert messages should include a short ID, title, source, source authority, why it matters, original link, and any grouped supporting sources.
- Daily digest messages should include already-alerted items, worth-reading items, saved items, official-source no-major-update notes where useful, source failures, and filtering statistics.
- CLI commands should support polling, daily report generation, rule testing, reclassification, and marking items read, saved, or ignored.
- Rule testing should run current rules against recent stored items and print what would alert, what would enter the digest, and what would be ignored.
- Reclassification should recompute importance and state for recent items without resending previous alerts by default.
- Feishu webhook URL and other secrets should be read from environment variables, not regular config.
- Local config should reference the environment variable names for secrets.
- Source and rule config should be safe to inspect and share after secrets are excluded.
- Code should be version controlled.
- Local secrets, local config, SQLite database, logs, and generated reports should not be committed.

Major modules to build:

- Source manifest module: validates source definitions and exposes typed source records.
- Fetching module: retrieves RSS, Atom, web pages, GitHub release data, changelog files, status feeds, and structured APIs where available.
- Extraction module: converts source-specific responses into normalized items.
- Fingerprint module: computes stable content fingerprints for meaningful fields only.
- Store module: persists sources, items, events, alerts, health checks, and item states.
- Deduplication module: collapses identical or near-identical items into canonical events.
- Classification module: applies authority, content type, keyword, cooldown, and source rules.
- Notification module: sends Feishu messages for strong alerts and daily digests.
- Report module: builds Markdown daily reports and message-friendly summaries.
- CLI module: exposes operational commands for poll, daily, test, reclassify, read, save, and ignore.
- Scheduler integration module: provides launchd-compatible commands and documented installation steps.

Deep modules to keep testable:

- The source manifest parser should encapsulate validation and prevent malformed sources from reaching fetchers.
- The normalized item extractor should hide source-specific parsing behind a stable output contract.
- The deduplication module should expose a simple item-to-event interface while hiding hard and approximate matching.
- The classifier should expose a deterministic classification interface and remain independent of network and notification code.
- The store should expose repository-style operations so database details do not leak into classification or notification logic.
- The notifier should accept prepared messages and remain independent of classification decisions.

## Testing Decisions

- Tests should focus on external behavior, not implementation details.
- Fetchers should be tested with fixture responses rather than live network calls.
- Extractors should be tested by feeding representative RSS, HTML, GitHub, changelog, pricing, model, and status fixtures and asserting normalized items.
- Fingerprinting should be tested to prove styling, scripts, image metadata, and recommendation blocks do not change content identity.
- Deduplication should be tested for identical URL, canonical URL, feed GUID, GitHub release tag, normalized title similarity, same vendor plus keyword within cooldown, and aggregator-to-official link merging.
- Classification should be tested as a pure deterministic module against source authority, source type, content type, keywords, and cooldown scenarios.
- Official-source critical events should test direct alert classification.
- Aggregator-only critical-looking events should test candidate classification unless they point to official or GitHub sources.
- Status incidents should test strong alert classification.
- Pricing, model, and deprecation changes should test strong alert classification.
- Ordinary research or opinion-like items should test daily-only classification unless they match AI programming, agent, security, or major model rules.
- Store tests should verify idempotent insert behavior and repeated polling without duplicate items.
- Event grouping tests should verify that later supporting sources update an existing event without creating a new alert.
- Notification tests should verify message payload shape without sending real Feishu requests.
- Daily report tests should verify grouping, saved item listing, alert listing, source failure listing, and filtering statistics.
- CLI tests should verify command behavior from the user's perspective, using a temporary database and fixture config.
- Rule testing command should be tested to confirm it reports would-alert, would-digest, and ignored outcomes without mutating alert history.
- Reclassification command should be tested to confirm it recomputes classification without resending previous alerts by default.
- Source health tests should verify failures are recorded and do not stop the whole poll run.
- Scheduler installation can be documented and smoke-tested manually on Mac mini after the CLI works.

There is no existing codebase test prior art in the current working directory. The implementation should therefore establish a small but meaningful test suite around the deep modules rather than trying to retrofit an existing project convention.

## Out of Scope

- No web UI or dashboard in the first version.
- No LLM summarization or LLM-based importance judgment in the first version.
- No automatic source discovery that adds new strong-alert sources without user approval.
- No personal WeChat bot, simulated WeChat login, or account automation.
- No email notification in the first version.
- No Feishu OAuth app or interactive Feishu card workflow in the first version.
- No mobile app.
- No browser extension.
- No full article archive.
- No scraping of comments, likes, repost counts, or social engagement metrics.
- No full HTML diff alerting.
- No broad KOL, X, Reddit, financing-news, or marketing-media monitoring in the first version.
- No production cloud deployment in the first version.
- No multi-user permission system.
- No automatic rule rewriting.
- No guarantee that every AI-related item on the internet is captured.

## Further Notes

First-version completion criteria:

1. Polling can fetch representative official, GitHub, and aggregator sources.
2. Anthropic coverage includes News, Engineering, Research, release notes, Claude Code changelog, desktop changelog, GitHub changelog, and status.
3. OpenAI, Qwen, DeepSeek, Mistral, Google DeepMind, AI HOT, and agents-radar have initial source entries or documented placeholders where parsing work remains.
4. New items are written to SQLite and repeated polling does not duplicate them.
5. Official-source critical events can send Feishu alerts.
6. Aggregator critical-looking events become candidates unless they point to official or GitHub sources.
7. Same-event items are merged and do not repeatedly alert within the cooldown window.
8. Morning daily report generation sends Feishu digest and writes Markdown locally.
9. Secret values are excluded from normal config and version control.
10. Source failures are recorded and surfaced in the daily digest.
11. Rule testing over recent items works.
12. Reclassification over recent items works without resending old alerts by default.
13. Read, save, and ignore item state commands work.
14. launchd setup is documented for every-10-minute polling and morning digest generation.

The first implementation should start with a narrow runnable slice before broadening the source list. A good tracer bullet is: source manifest, SQLite store, Anthropic Engineering extraction, Claude Code changelog extraction, AI HOT or agents-radar ingestion, deterministic classification, Feishu notifier, daily report, and basic CLI commands.

The PRD could not be published to an issue tracker because the current directory is not a Git repository and no issue tracker configuration exists. This document is therefore the local PRD artifact and carries `ready-for-agent` status.
