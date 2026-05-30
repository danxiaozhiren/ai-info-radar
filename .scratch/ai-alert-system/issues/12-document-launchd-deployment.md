# Document and smoke-test launchd deployment

Status: ready-for-human
Type: HITL
User stories covered: 1, 26, 30, 33, 42

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Document and smoke-test Mac mini deployment using scheduled command execution rather than a long-running web service. The documented setup should run polling every 10 minutes and morning digest generation once each morning, with local data, logs, reports, config, and secrets kept out of version control.

This is marked HITL because final verification needs the actual Mac mini environment and Feishu webhook.

## Acceptance criteria

- [ ] Documentation explains how to install the CLI environment on the Mac mini.
- [ ] Documentation explains how to configure local paths, local config, environment variables, and Feishu webhook secrets without committing them.
- [ ] Documentation includes launchd setup for every-10-minute polling.
- [ ] Documentation includes launchd setup for morning digest generation.
- [ ] A manual smoke test verifies that polling runs, logging works, source failures are visible, and the daily digest command can run.
- [ ] The repository ignores local secrets, local config, SQLite database files, logs, and generated reports.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/03-send-official-critical-feishu-alert.md
- .scratch/ai-alert-system/issues/04-generate-morning-digest.md
