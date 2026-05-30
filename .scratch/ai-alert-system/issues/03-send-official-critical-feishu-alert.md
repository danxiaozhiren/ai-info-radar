# Send one official-source critical Feishu alert

Status: ready-for-agent
Type: AFK
User stories covered: 2, 4, 14, 21, 31, 32, 33, 37, 40

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add deterministic classification and notification behavior for one official-source critical event. A user should be able to poll stored official items, classify a strong event such as a deprecation, migration, model release, pricing change, rate-limit change, security issue, outage, or major developer-tool update, and send a concise Feishu alert through a webhook configured outside normal source config.

The notifier should accept a prepared message and should not decide classification itself. Tests must verify payload shape without sending real Feishu requests.

## Acceptance criteria

- [ ] Classification combines source authority, content type, keyword rules, and event context into a deterministic alert decision.
- [ ] Official-source critical events can produce one strong alert with short ID, title, source, authority, why it matters, original link, and grouped supporting sources when present.
- [ ] Feishu webhook secrets are read from environment variables and are not required in regular config.
- [ ] The alert history records that the event was alerted so it is not sent repeatedly.
- [ ] The notifier can be tested without network access or real Feishu delivery.
- [ ] CLI output makes it clear when an alert was sent, skipped, or blocked by missing configuration.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
