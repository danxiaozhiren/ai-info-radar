# Source Code

The first MVP implementation lives in `src/ai_info_radar`.

The implementation should preserve the product hierarchy:

1. collect broadly across AI
2. judge source reliability
3. score broad importance, learning value, practice value, and focus fit
4. recommend what to verify, learn, try, monitor, or ignore

The current focus is a recommendation lens, not a collection boundary.

Current modules:

```text
src/
`-- ai_info_radar/
    |-- config.py        # YAML subset loader and typed config adapters
    |-- fetchers.py      # local JSON, RSS, web page, and GitHub Trending fetchers
    |-- models.py        # source, focus, scoring, item, and run data shapes
    |-- pipeline.py      # fetch -> dedupe -> score -> verify orchestration
    |-- recommendations.py # coverage classification and action recommendations
    |-- reporters.py     # Markdown Daily Radar writer
    |-- scoring.py       # heuristic MVP scoring model
    |-- verification.py  # source-tier confidence labels
    `-- cli.py           # command-line entrypoint
```

Keep the first implementation boring, observable, and easy to verify.

Run locally from the repository root:

```powershell
$env:PYTHONPATH="src"
python -m ai_info_radar --sources configs/sources.local.yaml --output outputs/daily-radar.md
```

Use `configs/sources.primary.yaml` to run against real primary RSS/Atom feeds.
Reports default to Chinese; pass `--language en` for the English template.
Use `configs/sources.leads.yaml` for discovery sources that should create
verification tasks rather than final conclusions.
