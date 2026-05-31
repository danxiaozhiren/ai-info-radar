# Merge same-event items with cooldown

Status: ready-for-agent
Type: AFK
User stories covered: 18, 19, 20, 21, 28

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Implement event grouping so duplicate or near-duplicate source items collapse into canonical events. Later supporting items should update the existing event and daily digest context without sending a fresh alert during the cooldown window.

The event grouping interface should hide hard and approximate matching details from classification and notification code.

## Acceptance criteria

- [x] Hard deduplication covers identical URL, canonical URL, feed ID, GitHub release tag, and source item ID.
- [x] Approximate deduplication covers normalized title similarity, same vendor plus strong keyword within a cooldown window, and aggregator links pointing to the same official source.
- [x] Later supporting sources update the existing event rather than creating a new event.
- [x] Alerts are sent once per event during the cooldown window.
- [x] The digest can show grouped supporting sources for an event.
- [x] Tests cover hard matching, approximate matching, aggregator-to-official merging, cooldown suppression, and later-source updates.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/05-ingest-aggregator-candidate-source.md

## Comments

- 2026-05-31: Implemented on branch `codex/issue-06-event-merge-cooldown`; verified with unit tests, CLI missing-webhook smoke test, and compile check.
