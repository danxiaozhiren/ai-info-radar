# Test and reclassify rules from CLI

Status: ready-for-agent
Type: AFK
User stories covered: 37, 38, 39, 44

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add CLI commands for testing current rules against recent stored items and reclassifying recent items after rule changes. Rule testing should show what would alert, what would enter the digest, and what would be ignored without mutating alert history. Reclassification should recompute classification and state for recent items without resending previous alerts by default.

This slice makes the rules tunable while preserving deterministic, non-LLM behavior.

## Acceptance criteria

- [ ] Rule configuration can be adjusted without code changes.
- [ ] A rule-test command reports would-alert, would-digest, candidate, and ignored outcomes for recent stored items.
- [ ] Rule testing does not mutate alert history or send notifications.
- [ ] A reclassify command recomputes recent item classification and state.
- [ ] Reclassification does not resend previous alerts by default.
- [ ] Tests cover rule-test output, non-mutating behavior, reclassification, and no-resend guarantees.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/03-send-official-critical-feishu-alert.md
