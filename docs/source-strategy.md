# Source Strategy

## Source Tiers

### Tier 1: Primary Sources

Use as fact anchors.

- official blogs
- official changelogs
- GitHub releases
- model cards
- papers
- benchmark sites
- product documentation

### Tier 2: Strong Signals

Useful for discovery and trend sensing.

- GitHub Trending
- Hugging Face models and papers
- arXiv feeds
- Hacker News discussions
- official company social accounts
- reputable technical blogs

### Tier 3: Lead Sources

Useful as leads, not conclusions.

- AI hot-list products
- KOL posts
- newsletters
- Reddit or community discussions
- Chinese AI media and communities

Lead sources are not default MVP inputs. They are optional comparison,
backfill, or discovery aids after the primary-source path is working.

### Tier 4: Noise Sources

Use only when there is a clear reason.

- repost-only content
- marketing pages without concrete claims
- summaries without original links
- emotional commentary
- low-context benchmark screenshots

## Source Rule

Lead sources can start investigation, but important conclusions should point
back to Tier 1 or Tier 2 sources whenever possible.

The core radar should not be built on processed hot lists or newsletters. Use
primary sources and stable structured feeds first; use lead sources only to
notice possible gaps in coverage.

The current registry separates source roles:

- `configs/sources.primary.yaml`: official RSS/Atom feeds and official source
  pages that can anchor facts.
- `configs/sources.leads.yaml`: discovery and analysis sources such as AI HOT
  or reputable media feeds. These should create verification tasks, not final
  conclusions.

## Coverage Rule

The source list should be broad before it is personalized.

The radar should maintain coverage across the major AI landscape, then use the
current focus to rank, explain, and recommend actions. A focus such as Browser
Use or AI Agent can add extra sources and boost related recommendations, but it
should not remove coverage for models, papers, infrastructure, products,
open-source projects, evals, safety, policy, or industry signals.

## Coverage Areas

- models and capabilities
- tools and products
- papers and concepts
- open source and developer ecosystem
- agents, Browser Use, computer use, MCP, automation
- AI coding
- RAG, memory, and retrieval
- multimodal AI
- evals and benchmarks
- infrastructure and deployment
- industry, policy, and adoption
- China and global AI ecosystems

## Recommendation Inputs

Each item should keep enough source metadata to explain why the radar recommends
it:

- source tier: primary, strong signal, lead
- source type: RSS, API, release feed, paper feed, web page, browser observation
- coverage area: models, research, tools, products, infrastructure, policy,
  safety, industry, open source, current focus
- verification status
- current focus fit

Recommendations should make the reason visible. For example:

- act now: high-importance item from a primary source with clear practical value
- study: high learning value or strong connection to the current focus
- try: hands-on source with code, API, demo, or reproducible steps
- verify: high-interest item from a lead or partially verified source
- monitor: potentially important but not yet actionable
