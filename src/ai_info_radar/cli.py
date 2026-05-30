from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import ManifestError
from .pipeline import poll_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-info-radar")
    subparsers = parser.add_subparsers(dest="command", required=True)

    poll_parser = subparsers.add_parser("poll", help="Poll configured AI information sources.")
    poll_parser.add_argument("--manifest", required=True, help="Path to source manifest JSON.")
    poll_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    poll_parser.add_argument("--repo-root", default=".", help="Repository root for relative fixtures.")
    poll_parser.add_argument("--timeout", type=float, default=10.0, help="Fetch timeout in seconds.")
    poll_parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")

    args = parser.parse_args(argv)
    if args.command == "poll":
        return _run_poll(args)
    parser.error(f"Unsupported command: {args.command}")
    return 2


def _run_poll(args: argparse.Namespace) -> int:
    try:
        result = poll_sources(
            manifest_path=Path(args.manifest),
            db_path=Path(args.db),
            repo_root=Path(args.repo_root),
            timeout_seconds=args.timeout,
        )
    except ManifestError as exc:
        print(f"manifest error: {exc}")
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "inserted": result.inserted,
                    "existing": result.existing,
                    "failures": result.failures,
                    "sources": [
                        {
                            "source_id": item.source_id,
                            "ok": item.ok,
                            "inserted": item.inserted,
                            "existing": item.existing,
                            "message": item.message,
                        }
                        for item in result.results
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(
            f"poll complete: inserted={result.inserted} "
            f"existing={result.existing} failures={result.failures}"
        )
        for source_result in result.results:
            status = "ok" if source_result.ok else "failed"
            print(
                f"- {source_result.source_id}: {status}; "
                f"inserted={source_result.inserted}; "
                f"existing={source_result.existing}; {source_result.message}"
            )

    return 0
