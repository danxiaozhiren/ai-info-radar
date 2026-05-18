# Architecture

## Pipeline

```text
source registry
  ->
fetchers
  ->
normalizer
  ->
deduplicator
  ->
scorer
  ->
verifier
  ->
report writer
  ->
learning/practice backlog
```

## Fetching Strategy

1. Prefer official APIs, RSS, release feeds, model cards, paper metadata, and
   other structured sources.
2. Use browser automation when a source has no clean interface, requires
   interaction, or needs original-page verification.
3. Store source URL, source type, fetch time, and evidence notes with every
   item.

## Data Shape

Each normalized item should keep:

- title
- url
- source name
- source tier
- published time
- fetched time
- summary
- claims
- tags
- raw category
- related focus topics
- global importance score
- learning value score
- practice value score
- current focus fit score
- confidence
- verification status

## Report Types

Daily radar:

- short, broad, high-signal update
- maximum 10 to 15 items
- focuses on what changed

Weekly learning map:

- slower synthesis
- identifies themes, concepts, and practice tasks
- updates the personal learning route

## Browser Use Role

Browser Use should be a selective capability.

Good uses:

- dynamic pages without stable APIs
- product changelog pages
- source pages requiring navigation or expansion
- comparing rendered page content with API output
- capturing evidence and failure notes

Bad uses:

- bulk crawling stable feeds
- replacing official APIs
- extracting facts from pages without source verification
- treating browser observations as final truth when original data is available
