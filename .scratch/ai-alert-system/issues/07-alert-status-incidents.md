# Alert on status incidents and recoveries

Status: ready-for-agent
Type: AFK
User stories covered: 8, 9, 15, 21, 29

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add status-page monitoring for incidents, outages, degradations, and recovery events from at least one official model or developer-platform status source. A user should receive a strong Feishu alert for meaningful incidents, and the daily digest should show incident and source-health context.

Structured status feeds or APIs should be preferred where available.

## Acceptance criteria

- [ ] The curated manifest includes at least one official status source.
- [ ] The status extractor normalizes incident, degradation, outage, and recovery records into items or events.
- [ ] Status incidents and recoveries can trigger direct strong alerts from official sources.
- [ ] Source failures and stale status retrievals are recorded for daily digest visibility.
- [ ] Repeated polling of the same incident is idempotent and does not repeatedly alert.
- [ ] Tests cover status fixtures, incident classification, recovery classification, and failure reporting.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/03-send-official-critical-feishu-alert.md
