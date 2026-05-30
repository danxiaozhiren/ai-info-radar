# Manage item state from CLI

Status: ready-for-agent
Type: AFK
User stories covered: 23, 24, 25

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add CLI commands that let the user mark stored items as read, saved, or ignored and inspect those states in the daily workflow. Saved items should appear separately in the digest; ignored items should not keep reappearing as normal new work; read state should help the user manage what has already been seen.

This slice keeps the first version operational without adding a web UI.

## Acceptance criteria

- [ ] Stored items support at least new, alerted, in daily, read, saved, and ignored states.
- [ ] CLI commands can mark one or more items read, saved, or ignored by stable identifiers.
- [ ] Saved items appear in a distinct daily digest section.
- [ ] Ignored items are excluded from normal alert or digest surfaces unless explicitly requested.
- [ ] State changes are persisted and survive repeated CLI runs.
- [ ] Tests cover state transitions, digest inclusion or exclusion, and user-facing CLI behavior with a temporary database.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/04-generate-morning-digest.md
