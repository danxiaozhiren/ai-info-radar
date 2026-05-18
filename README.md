# AI Info Radar

AI Info Radar is a personal AI frontier radar for learning and practice.

It continuously tracks new AI models, tools, papers, products, open-source
projects, and industry signals, then turns noisy information into verified
sources, learning topics, and practical next actions.

## Positioning

AI Info Radar is not an AI hot list, a news scraper, or a narrow Agent-only
digest.

It is built around two ideas:

1. Wide-angle AI awareness

   Stay close to the full AI frontier, not only the current learning topic.

2. Adjustable learning focus

   Highlight items related to the current focus, such as Browser Use, AI Agent,
   RAG, multimodal AI, AI coding, model evaluation, or any future learning
   direction.

The current focus is Browser Use and AI Agent, but the product boundary is the
broader AI world.

## Core Questions

Each radar run should help answer:

- What changed in AI today or this week?
- Which items are globally important?
- Which items are worth learning?
- Which items are worth trying hands-on?
- Which claims need verification from original sources?
- Which noisy items can be ignored for now?

## Output Principles

- Prefer original sources over second-hand summaries.
- Separate facts, interpretations, and speculation.
- Keep source links with every important item.
- Score both broad AI importance and personal learning value.
- Use Browser Use only where browser observation or interaction adds value.
- Turn important signals into learning notes or practice tasks.

## Repository Map

```text
ai-info-radar/
|-- configs/        # Source, focus, and scoring examples
|-- data/           # Local raw/intermediate data
|-- docs/           # Product, architecture, and strategy notes
|-- labs/           # Browser Use and source-evaluation experiments
|-- outputs/        # Generated daily/weekly radar reports
|-- prompts/        # Ranking, verification, and briefing prompts
`-- src/            # Implementation will live here
```

## First MVP

The first version should generate a short Markdown briefing from a small set of
high-value sources.

It should cover the broad AI frontier while giving extra weight to the current
learning focus.

```text
sources
  ->
fetchers
  ->
normalizer
  ->
deduplicator
  ->
scorer
  ->
source verification
  ->
daily radar / weekly learning map
```

## Relationship To Browser Use

Browser Use is an important implementation capability and a current learning
focus, not the product boundary.

Good Browser Use tasks include:

- observing dynamic pages without stable APIs
- checking original source pages
- comparing page content with API output
- collecting evidence from product changelogs
- recording failures and verification notes

Structured feeds and APIs should still be preferred when they are more stable.
