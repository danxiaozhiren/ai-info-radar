# Persist one Anthropic Engineering poll end-to-end

Status: ready-for-agent
Type: AFK
User stories covered: 1, 7, 16, 17, 22, 34, 35, 40, 42, 44

## Parent

.scratch/ai-alert-system/PRD.md

## What to build

Implement the narrowest runnable poll path for Anthropic Engineering as an official source. A user should be able to run the CLI once, fetch or parse the source through the curated manifest, normalize meaningful content fields, persist new items in SQLite, record source health, and run the same command again without creating duplicates.

This slice establishes the first durable vertical path for the AI information gate: curated source definition, source retrieval, content extraction, meaningful-field fingerprinting, storage, idempotency, source health visibility, and CLI operation. It should not send notifications yet.

## Acceptance criteria

- [x] A curated Anthropic Engineering source entry can be loaded and validated by the source manifest.
- [x] Running the poll command stores normalized items with source, vendor, content type, original URL, detected time, published time when available, fingerprint, and trace metadata.
- [x] Re-running the poll command against the same fixture or live response does not duplicate stored items.
- [x] HTML styling, scripts, image metadata, footer content, and recommendation blocks do not affect the content fingerprint.
- [x] Source failures are recorded without stopping the entire poll run.
- [x] Tests cover manifest validation, extraction, fingerprinting, SQLite idempotency, and CLI behavior with fixtures.

## Blocked by

None - can start immediately

## Comments

- 2026-05-30: Implemented on branch `codex/issue-01-anthropic-poll`; verified with unit tests, CLI idempotency smoke test, and compile check.
