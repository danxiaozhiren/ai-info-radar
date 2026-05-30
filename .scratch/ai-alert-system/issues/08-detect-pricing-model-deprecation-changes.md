# Detect pricing, model-list, and deprecation changes

Status: ready-for-agent
Type: AFK
User stories covered: 12, 13, 14, 16, 17

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add meaningful-field extraction and fingerprinting for pricing, model-list, and deprecation or migration pages. The system should detect substantive changes such as model additions, removals, deprecations, context-length changes, capability changes, input or output price changes, rate-limit changes, and migration notices while ignoring layout and page-chrome churn.

This slice should produce stored change items that can be classified as strong alerts by existing alert rules.

## Acceptance criteria

- [ ] At least one pricing, model-list, or deprecation source can be represented in the curated manifest.
- [ ] Meaningful fields are extracted into normalized records rather than full-page HTML diffs.
- [ ] Fingerprints change when substantive pricing, model, capability, context, rate-limit, deprecation, or migration fields change.
- [ ] Fingerprints do not change for styling, scripts, image metadata, recommendations, or footer changes.
- [ ] Substantive official-source changes can be classified as strong alerts.
- [ ] Tests cover fixture changes for substantive updates and non-content churn.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/03-send-official-critical-feishu-alert.md
