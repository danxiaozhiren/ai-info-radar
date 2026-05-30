# Poll Claude Code changelog as developer-tool signal

Status: ready-for-agent
Type: AFK
User stories covered: 7, 8, 11, 14, 17

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Extend the polling path to cover the Claude Code changelog as a high-priority developer-tool source. A user should be able to run the poll command and see newly added changelog entries stored as normalized items, with stable fingerprints that focus on version sections and substantive release notes rather than page chrome.

This slice proves that the system can monitor developer changelogs, not only article indexes.

## Acceptance criteria

- [ ] The curated manifest includes a Claude Code changelog source with an appropriate official authority level and content type.
- [ ] The extractor identifies newly added changelog entries or version sections as normalized items.
- [ ] Stored items preserve original links, source identity, detected time, and useful trace metadata.
- [ ] Re-running the same changelog input is idempotent.
- [ ] Breaking changes, migrations, deprecations, MCP, agent workflow, and developer-tool terms are detectable by downstream classification inputs.
- [ ] Tests cover representative changelog fixtures and repeated polling behavior.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
