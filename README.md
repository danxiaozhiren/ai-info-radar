# AI Info Radar

AI Info Radar is a broad and comprehensive AI information radar for learning
and practice.

It continuously tracks new AI models, capabilities, papers, products,
developer tools, open-source projects, infrastructure, benchmarks, policy,
safety signals, and industry changes, then turns noisy information into
source-aware recommendations, learning topics, and practical next actions.

## Positioning

AI Info Radar is not an AI hot list, a news scraper, or a narrow Agent-only
digest. It should be wide by default.

It is built around three ideas:

1. Comprehensive AI awareness

   Track the full AI landscape, not only the current learning topic.

2. Source-aware judgment

   Treat original sources, strong signals, and lead sources differently. The
   radar should say how much confidence each recommendation deserves.

3. Adjustable personal focus

   Use the current focus, such as Browser Use, AI Agent, RAG, multimodal AI, AI
   coding, model evaluation, or any future learning direction, to shape
   recommendations and suggested actions.

The current focus is Browser Use and AI Agent, but that focus is only a lens.
The product boundary is the whole AI world.

## Core Questions

Each radar run should help answer:

- What changed in AI today or this week?
- Which items are globally important?
- Which areas of AI are changing fastest?
- Which sources are reliable enough to act on?
- Which items are worth learning?
- Which items are worth trying hands-on?
- Which claims need verification from original sources?
- What should I do next given my current focus?
- Which noisy items can be ignored for now?

## Output Principles

- Prefer original sources over second-hand summaries.
- Separate facts, interpretations, and speculation.
- Keep source links with every important item.
- Keep broad AI coverage before applying the personal-focus lens.
- Score both broad AI importance and personal learning value.
- Use source quality and current focus together when generating
  recommendations.
- Use Browser Use only where browser observation or interaction adds value.
- Turn important signals into learning notes or practice tasks.
- Do not make processed hot lists or newsletters the default source of truth.

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

The first version should generate a short Markdown daily radar from a small set of
high-value sources. Even when the source set is small, the product shape should
remain broad: models, research, products, open source, tooling, infrastructure,
benchmarks, policy, safety, and industry signals should all have a place in the
radar.

The daily radar should treat the configured report date as the main event
window. Items published or updated on that date go into the main "today" section;
older items discovered during the run are backfill; lead-source items stay in a
verification section until the original source is checked.

It should first cover the broad AI frontier, then use source quality and the
current learning focus to decide what to recommend, verify, study, try, or
ignore.

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

The current MVP implements the daily-radar path with a deterministic local
sample source so the full pipeline can be tested without network access. The
next source milestone is primary-source-first collection across the broad AI
landscape, not hot-list aggregation.

```powershell
$env:PYTHONPATH="src"
python -m ai_info_radar --sources configs/sources.local.yaml --output outputs/daily-radar.md --date 2026-05-19
```

Run against the primary-source feed set:

```powershell
$env:PYTHONPATH="src"
python -m ai_info_radar --sources configs/sources.primary.yaml --output outputs/daily-radar.md --date 2026-05-19 --max-per-source 3 --max-age-days 30
```

Run against lead and strong-signal discovery sources:

```powershell
$env:PYTHONPATH="src"
python -m ai_info_radar --sources configs/sources.leads.yaml --output outputs/daily-radar-leads.md --date 2026-05-19
```

Reports default to Chinese. Pass `--language en` only when an English report is
needed.

Run tests:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```

## Relationship To Browser Use

Browser Use is an important implementation capability and a current learning
focus, not the product boundary. The radar should still collect and judge the
whole AI landscape before applying the Browser Use / AI Agent lens to
recommendations.

Good Browser Use tasks include:

- observing dynamic pages without stable APIs
- checking original source pages
- comparing page content with API output
- collecting evidence from product changelogs
- recording failures and verification notes

Structured feeds and APIs should still be preferred when they are more stable.
