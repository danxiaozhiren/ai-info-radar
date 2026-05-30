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

- [ ] Hard deduplication covers identical URL, canonical URL, feed ID, GitHub release tag, and source item ID.
- [ ] Approximate deduplication covers normalized title similarity, same vendor plus strong keyword within a cooldown window, and aggregator links pointing to the same official source.
- [ ] Later supporting sources update the existing event rather than creating a new event.
- [ ] Alerts are sent once per event during the cooldown window.
- [ ] The digest can show grouped supporting sources for an event.
- [ ] Tests cover hard matching, approximate matching, aggregator-to-official merging, cooldown suppression, and later-source updates.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/05-ingest-aggregator-candidate-source.md
