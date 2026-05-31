# Expand curated official-source manifest

Status: done
Type: AFK
User stories covered: 8, 9, 10, 11, 34, 35, 36

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Expand the curated manifest to cover the first-version official-source map across Anthropic, OpenAI, Qwen, DeepSeek, Mistral, Google DeepMind, AI programming tools, Agent workflow sources, GitHub releases, developer changelogs, status, pricing, model lists, and documented placeholders where parsing is not yet implemented.

The goal is source governance and coverage visibility, not automatic crawling.

## Acceptance criteria

- [x] Anthropic coverage includes News, Engineering, Research, release notes, Claude Code changelog, desktop changelog, GitHub changelog, and status.
- [x] OpenAI coverage includes official news, status, docs changelog, pricing, model, and relevant GitHub-related sources where available.
- [x] Qwen, DeepSeek, Mistral, and Google DeepMind have initial official entries or documented placeholders.
- [x] AI programming and Agent workflow sources include Codex, Claude Code, Cursor, OpenCode, MCP, Agents SDK, GitHub Copilot, and related tool sources where suitable.
- [x] Each manifest entry records source name, vendor, source type, authority level, URL, priority, parsing strategy, and enabled status.
- [x] Manifest validation rejects malformed, unapproved, or incomplete source entries.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md

## Agent notes

- 2026-05-31: Implemented on branch `codex/issue-09-official-source-manifest`. Verified with 51 unit tests, a disabled-manifest poll smoke test (`inserted=0 existing=0 failures=0`), and a `compileall` check.
