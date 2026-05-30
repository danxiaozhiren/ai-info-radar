# Ingest AI HOT or agents-radar as candidate source

Status: ready-for-agent
Type: AFK
User stories covered: 5, 6, 18, 19, 34, 36

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add one curated aggregator source, either AI HOT or agents-radar, as a candidate and supplement source. Aggregator items should be stored and available for daily summaries or event support, but they should not by themselves trigger a strong alert unless they point to an official or original GitHub source.

This slice broadens discovery while preserving the rule that official sources and original repositories are the facts of record.

## Acceptance criteria

- [ ] The curated manifest includes one aggregator source with a non-official authority level.
- [ ] The aggregator extractor stores normalized candidate items with original aggregator link and linked target where available.
- [ ] Aggregator-only critical-looking items are classified as candidates, not direct strong alerts.
- [ ] Aggregator items that point to official or original GitHub targets can support an existing event.
- [ ] New aggregator sources still require manual manifest changes rather than automatic approval.
- [ ] Tests cover aggregator extraction, candidate classification, and official-target linking behavior.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
