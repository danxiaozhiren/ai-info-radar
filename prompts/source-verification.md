# Source Verification Prompt

You are verifying an AI news item before it enters the radar.

## Task

Given a candidate item and its source links, classify what is fact, what is
interpretation, and what remains unverified.

## Checks

- Is there an original source?
- Does the source support the title?
- Are claims from a primary source, a strong signal source, or only a lead
  source?
- Does the item include concrete changes, code, release notes, paper details,
  benchmark data, or product behavior?
- What should be checked manually?

## Output

```md
Source tier:
Verification status:
Supported facts:
Interpretation:
Unverified claims:
Suggested confidence:
Next action:
```
