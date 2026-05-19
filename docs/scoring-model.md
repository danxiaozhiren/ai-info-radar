# Scoring Model

## Goal

Keep the radar broad without becoming noisy, then turn the broad scan into
personal recommendations.

The scoring model should let globally important AI changes surface even when
they are not related to the current learning focus. The current focus should
shape advice and actions, not hide the rest of AI.

## Core Scores

### World Value

How important is this item to the AI world?

Signals:

- major model or capability change
- new research direction
- broad developer impact
- ecosystem adoption
- strong benchmark movement
- major product or policy change

### Learning Value

How useful is this item for building AI knowledge?

Signals:

- teaches a concept
- clarifies a mechanism
- explains a trend
- connects multiple areas
- fills a known knowledge gap

### Practice Value

How useful is this item for hands-on practice?

Signals:

- can be installed or tested
- has code, API, demo, or reproducible steps
- suggests a small experiment
- can update a project backlog

### Current Focus Fit

How relevant is this item to the current learning focus?

This score should boost, not dominate. A high focus score should usually change
the recommendation, for example from "monitor" to "try hands-on", but a low
focus score should not suppress a major model, research, safety, policy, or
industry signal.

Current focus is configured in `configs/focus.example.yaml`.

## Suggested Weighted Score

```text
final_score =
  world_value * 0.35 +
  learning_value * 0.25 +
  practice_value * 0.20 +
  current_focus_fit * 0.20
```

For major AI events, world value can override weak focus fit.

## Source-Aware Recommendations

Source quality is not the same as importance.

Source quality should influence:

- confidence level
- verification status
- whether the item can be treated as fact
- whether the recommendation is "act", "study", "try", "monitor", or "verify"

Current focus should influence:

- suggested next action
- whether to add the item to the learning map
- whether to turn the item into a practice task
- how prominently it appears in focus-specific sections

The recommendation is the intersection of:

```text
recommendation =
  broad AI importance
  + source confidence
  + learning/practice value
  + current focus fit
```

## Confidence

Confidence is separate from importance.

Use:

- high: primary source or multiple reliable sources
- medium: strong signal source with partial verification
- low: lead source, unclear source, or unverified claim

## Output Labels

- must_read
- worth_learning
- worth_trying
- monitor
- ignore_for_now
- needs_verification
