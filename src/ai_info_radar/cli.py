from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_daily_radar, write_daily_radar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an AI Info Radar Markdown briefing.")
    parser.add_argument("--sources", default="configs/sources.local.yaml", help="Path to sources YAML.")
    parser.add_argument("--focus", default="configs/focus.example.yaml", help="Path to focus YAML.")
    parser.add_argument("--scoring", default="configs/scoring.example.yaml", help="Path to scoring YAML.")
    parser.add_argument("--output", default="outputs/daily-radar.md", help="Markdown output path.")
    parser.add_argument(
        "--language",
        choices=("zh", "en"),
        default="zh",
        help="Report language. Defaults to Chinese.",
    )
    parser.add_argument("--max-items", type=int, default=15, help="Maximum number of ranked items.")
    parser.add_argument(
        "--date",
        default=None,
        help="Radar date in YYYY-MM-DD. Defaults to today in Asia/Shanghai.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        help="Backfill lookback window in days. Use 0 to disable age filtering.",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=0,
        help="Maximum ranked items per source. Use 0 to disable the cap.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Network fetch timeout in seconds.")
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    run = run_daily_radar(
        sources_path=args.sources,
        focus_path=args.focus,
        scoring_path=args.scoring,
        repo_root=repo_root,
        max_items=args.max_items,
        max_age_days=args.max_age_days or None,
        max_per_source=args.max_per_source or None,
        timeout_seconds=args.timeout,
        report_date=args.date,
    )
    write_daily_radar(run, args.output, language=args.language)
    print(f"Wrote {args.output} with {len(run.items)} item(s).")
    if run.fetch_errors:
        print(f"Fetch notes: {len(run.fetch_errors)} source(s) reported errors.")
    return 0
