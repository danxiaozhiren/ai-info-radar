# Source Verification Prompt

You are verifying an AI information item before it enters the radar.

## Task

Given a candidate item and its source links, classify what is fact, what is
interpretation, and what remains unverified. Then explain whether the item is
broadly important, mainly relevant to the current focus, or only a weak lead.

## Checks

- Is there an original source?
- Does the source support the title?
- Are claims from a primary source, a strong signal source, or only a lead
  source?
- Does the item include concrete changes, code, release notes, paper details,
  benchmark data, or product behavior?
- What should be checked manually?
- Does the recommendation come from source strength, broad AI importance,
  current focus fit, or hands-on value?

## Output

```md
Source tier:
Verification status:
Supported facts:
Interpretation:
Unverified claims:
Suggested confidence:
Recommendation reason:
Next action:
```
