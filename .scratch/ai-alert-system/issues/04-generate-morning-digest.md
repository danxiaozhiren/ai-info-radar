# Generate morning digest from stored events

Status: ready-for-agent
Type: AFK
User stories covered: 3, 22, 25, 26, 27, 28, 29, 31

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add a daily digest command that reads stored items, events, alert history, source health, and item state, then writes a local Markdown report and sends a Feishu-friendly morning digest. The digest should summarize already-alerted items, worth-reading items, saved items, source failures, and filtering statistics without storing full article text.

This slice makes the non-interrupting daily workflow useful even when no strong alert fires.

## Acceptance criteria

- [ ] The daily command writes a Markdown report to a local reports location.
- [ ] The daily command prepares a Feishu-friendly digest message that can be sent through the same webhook mechanism.
- [ ] The report includes already-alerted items, worth-reading items, saved items, source failures, and filtering statistics.
- [ ] Original links are retained and full article text is not stored or reproduced.
- [ ] Items included in the digest receive an appropriate state update without overwriting read, saved, or ignored state incorrectly.
- [ ] Tests cover digest grouping, saved item listing, alert listing, source failure listing, filtering statistics, and notification payload shape.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/03-send-official-critical-feishu-alert.md
