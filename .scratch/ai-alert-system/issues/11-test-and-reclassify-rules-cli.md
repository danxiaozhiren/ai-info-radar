# Test and reclassify rules from CLI

Status: done
Type: AFK
User stories covered: 37, 38, 39, 44

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Add CLI commands for testing current rules against recent stored items and reclassifying recent items after rule changes. Rule testing should show what would alert, what would enter the digest, and what would be ignored without mutating alert history. Reclassification should recompute classification and state for recent items without resending previous alerts by default.

This slice makes the rules tunable while preserving deterministic, non-LLM behavior.

## Acceptance criteria

- [x] Rule configuration can be adjusted without code changes.
- [x] A rule-test command reports would-alert, would-digest, candidate, and ignored outcomes for recent stored items.
- [x] Rule testing does not mutate alert history or send notifications.
- [x] A reclassify command recomputes recent item classification and state.
- [x] Reclassification does not resend previous alerts by default.
- [x] Tests cover rule-test output, non-mutating behavior, reclassification, and no-resend guarantees.

## Blocked by

- .scratch/ai-alert-system/issues/01-persist-anthropic-engineering-poll.md
- .scratch/ai-alert-system/issues/03-send-official-critical-feishu-alert.md

## Agent notes

- 2026-05-31: Implemented on branch `codex/issue-11-rules-cli`. Added JSON-backed rule loading, `rule-test` and `reclassify` CLI commands, optional `--rules` support for alerting, non-mutating rule previews, and no-resend-aware state recomputation. Verified with 60 unit tests, rule-test/reclassify CLI smoke checks, and a `compileall` check.
