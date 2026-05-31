from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .alerts import send_next_critical_alert
from .classifier import RulesError, load_rules
from .digest import generate_daily_digest
from .manifest import ManifestError
from .models import StoredItem
from .pipeline import poll_sources
from .rule_engine import (
    ReclassifyUpdate,
    RuleTestItem,
    reclassify_recent_items,
    summarize_outcomes,
    test_recent_items,
)
from .store import ITEM_STATES, ItemStateError, ItemStateUpdate, RadarStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-info-radar")
    subparsers = parser.add_subparsers(dest="command", required=True)

    poll_parser = subparsers.add_parser("poll", help="Poll configured AI information sources.")
    poll_parser.add_argument("--manifest", required=True, help="Path to source manifest JSON.")
    poll_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    poll_parser.add_argument("--repo-root", default=".", help="Repository root for relative fixtures.")
    poll_parser.add_argument("--timeout", type=float, default=10.0, help="Fetch timeout in seconds.")
    poll_parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")

    alert_parser = subparsers.add_parser("alert", help="Send one critical Feishu alert.")
    alert_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    alert_parser.add_argument(
        "--webhook-env",
        default="FEISHU_WEBHOOK_URL",
        help="Environment variable containing the Feishu webhook URL.",
    )
    alert_parser.add_argument("--timeout", type=float, default=10.0, help="Webhook timeout in seconds.")
    alert_parser.add_argument("--rules", help="Optional JSON rules config.")
    alert_parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")

    daily_parser = subparsers.add_parser("daily", help="Write and optionally send a morning digest.")
    daily_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    daily_parser.add_argument("--reports-dir", default="reports", help="Directory for Markdown reports.")
    daily_parser.add_argument(
        "--webhook-env",
        default="FEISHU_WEBHOOK_URL",
        help="Environment variable containing the Feishu webhook URL.",
    )
    daily_parser.add_argument("--timeout", type=float, default=10.0, help="Webhook timeout in seconds.")
    daily_parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")

    items_parser = subparsers.add_parser("items", help="Inspect and update stored item states.")
    item_subparsers = items_parser.add_subparsers(dest="items_command", required=True)

    list_parser = item_subparsers.add_parser("list", help="List stored items and their states.")
    list_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    list_parser.add_argument(
        "--state",
        default="all",
        choices=["all", *sorted(ITEM_STATES)],
        help="Filter by item state.",
    )
    list_parser.add_argument("--json", action="store_true", help="Print machine-readable item list.")

    for command, target_state in (("read", "read"), ("save", "saved"), ("ignore", "ignored")):
        mark_parser = item_subparsers.add_parser(command, help=f"Mark items as {target_state}.")
        mark_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
        mark_parser.add_argument(
            "identifiers",
            nargs="+",
            help="Item ids or fingerprint prefixes shown by 'items list'.",
        )
        mark_parser.add_argument("--json", action="store_true", help="Print machine-readable update summary.")
        mark_parser.set_defaults(target_state=target_state)

    rule_test_parser = subparsers.add_parser("rule-test", help="Preview rule outcomes without side effects.")
    rule_test_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    rule_test_parser.add_argument("--rules", help="Optional JSON rules config.")
    rule_test_parser.add_argument("--limit", type=int, default=20, help="Number of recent items to inspect.")
    rule_test_parser.add_argument("--json", action="store_true", help="Print machine-readable rule report.")

    reclassify_parser = subparsers.add_parser("reclassify", help="Recompute item states from current rules.")
    reclassify_parser.add_argument("--db", required=True, help="Path to local SQLite database.")
    reclassify_parser.add_argument("--rules", help="Optional JSON rules config.")
    reclassify_parser.add_argument("--limit", type=int, default=20, help="Number of recent items to reclassify.")
    reclassify_parser.add_argument(
        "--include-user-states",
        action="store_true",
        help="Also overwrite read, saved, and ignored items.",
    )
    reclassify_parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")

    args = parser.parse_args(argv)
    if args.command == "poll":
        return _run_poll(args)
    if args.command == "alert":
        return _run_alert(args)
    if args.command == "daily":
        return _run_daily(args)
    if args.command == "items":
        return _run_items(args)
    if args.command == "rule-test":
        return _run_rule_test(args)
    if args.command == "reclassify":
        return _run_reclassify(args)
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


def _run_alert(args: argparse.Namespace) -> int:
    try:
        rules = load_rules(args.rules)
    except (RulesError, OSError, ValueError) as exc:
        print(f"rules error: {exc}")
        return 2

    result = send_next_critical_alert(
        db_path=Path(args.db),
        webhook_url=os.environ.get(args.webhook_env),
        rules=rules,
        timeout_seconds=args.timeout,
    )

    summary = {
        "status": result.status,
        "sent": result.sent,
        "message": result.message,
        "alert_key": result.alert_key,
        "short_id": result.short_id,
        "title": result.title,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    elif result.status == "sent":
        print(f"alert sent: {result.short_id} {result.title}")
    elif result.status == "skipped":
        print(f"alert skipped: {result.message}")
    elif result.status == "blocked":
        print(f"alert blocked: {result.message}; set {args.webhook_env}")
    else:
        print(f"alert failed: {result.message}")

    return 0 if result.status in {"sent", "skipped"} else 1


def _run_daily(args: argparse.Namespace) -> int:
    result = generate_daily_digest(
        db_path=Path(args.db),
        reports_dir=Path(args.reports_dir),
        webhook_url=os.environ.get(args.webhook_env),
        timeout_seconds=args.timeout,
    )

    summary = {
        "status": result.status,
        "sent": result.sent,
        "message": result.message,
        "report_path": str(result.report_path),
        "marked_digested": result.marked_digested,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    elif result.status == "sent":
        print(f"daily digest sent: {result.report_path}")
    elif result.status == "prepared":
        print(f"daily digest prepared: {result.report_path}; {result.message}")
    else:
        print(f"daily digest failed: {result.message}; report={result.report_path}")

    return 0 if result.status in {"sent", "prepared"} else 1


def _run_items(args: argparse.Namespace) -> int:
    if args.items_command == "list":
        return _run_items_list(args)
    if args.items_command in {"read", "save", "ignore"}:
        return _run_items_mark(args)
    print(f"unsupported items command: {args.items_command}")
    return 2


def _run_items_list(args: argparse.Namespace) -> int:
    try:
        with RadarStore(Path(args.db)) as store:
            state = None if args.state == "all" else args.state
            items = store.list_items(state=state)
    except ItemStateError as exc:
        print(f"item state error: {exc}")
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "count": len(items),
                    "items": [_item_summary(item) for item in items],
                    "state": args.state,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    print(f"items: count={len(items)} state={args.state}")
    for item in items:
        print(
            f"- #{item.id} {item.fingerprint[:10]} state={item.state} "
            f"{item.title} ({item.source_name})"
        )
    return 0


def _run_items_mark(args: argparse.Namespace) -> int:
    try:
        with RadarStore(Path(args.db)) as store:
            updates = store.set_item_state_by_identifiers(args.identifiers, args.target_state)
    except ItemStateError as exc:
        print(f"item state error: {exc}")
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "requested": len(args.identifiers),
                    "state": args.target_state,
                    "updated": len(updates),
                    "items": [_item_update_summary(update) for update in updates],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    print(
        f"items updated: state={args.target_state} "
        f"updated={len(updates)} requested={len(args.identifiers)}"
    )
    for update in updates:
        item = update.item
        print(
            f"- #{item.id} {item.fingerprint[:10]} "
            f"{update.previous_state}->{update.new_state} {item.title}"
        )
    return 0


def _item_summary(item: StoredItem) -> dict[str, object]:
    return {
        "id": item.id,
        "short_id": item.fingerprint[:10],
        "state": item.state,
        "title": item.title,
        "source_name": item.source_name,
        "url": item.url,
    }


def _item_update_summary(update: ItemStateUpdate) -> dict[str, object]:
    summary = _item_summary(update.item)
    summary["previous_state"] = update.previous_state
    summary["state"] = update.new_state
    return summary


def _run_rule_test(args: argparse.Namespace) -> int:
    try:
        rules = load_rules(args.rules)
        with RadarStore(Path(args.db)) as store:
            items = test_recent_items(store, rules=rules, limit=args.limit)
    except (ItemStateError, RulesError, OSError, ValueError) as exc:
        print(f"rules error: {exc}")
        return 2

    summary = summarize_outcomes(items)
    if args.json:
        print(
            json.dumps(
                {
                    "count": len(items),
                    "summary": summary,
                    "items": [_rule_test_summary(item) for item in items],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    print(f"rule-test: count={len(items)}")
    print(_format_outcome_summary(summary))
    for item in items:
        stored = item.item
        print(
            f"- #{stored.id} {stored.fingerprint[:10]} outcome={item.outcome} "
            f"severity={item.decision.severity} score={item.decision.score} "
            f"state={stored.state} {stored.title}"
        )
    return 0


def _run_reclassify(args: argparse.Namespace) -> int:
    try:
        rules = load_rules(args.rules)
        with RadarStore(Path(args.db)) as store:
            updates = reclassify_recent_items(
                store,
                rules=rules,
                limit=args.limit,
                include_user_states=args.include_user_states,
            )
    except (ItemStateError, RulesError, OSError, ValueError) as exc:
        print(f"rules error: {exc}")
        return 2

    changed = sum(1 for update in updates if update.changed)
    preserved = sum(1 for update in updates if update.preserved)
    summary = summarize_outcomes(updates)
    if args.json:
        print(
            json.dumps(
                {
                    "changed": changed,
                    "count": len(updates),
                    "preserved": preserved,
                    "summary": summary,
                    "items": [_reclassify_summary(update) for update in updates],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    print(f"reclassified: count={len(updates)} changed={changed} preserved={preserved}")
    print(_format_outcome_summary(summary))
    for update in updates:
        item = update.item
        print(
            f"- #{item.id} {item.fingerprint[:10]} {update.previous_state}->{update.new_state} "
            f"outcome={update.outcome} severity={update.decision.severity} {item.title}"
        )
    return 0


def _rule_test_summary(item: RuleTestItem) -> dict[str, object]:
    stored = item.item
    return {
        **_item_summary(stored),
        "matched_terms": list(item.decision.matched_terms),
        "outcome": item.outcome,
        "reasons": list(item.decision.reasons),
        "score": item.decision.score,
        "severity": item.decision.severity,
        "would_alert": item.decision.should_alert,
    }


def _reclassify_summary(update: ReclassifyUpdate) -> dict[str, object]:
    return {
        **_rule_test_summary(
            RuleTestItem(
                item=update.item,
                decision=update.decision,
                outcome=update.outcome,
            )
        ),
        "changed": update.changed,
        "new_state": update.new_state,
        "preserved": update.preserved,
        "previous_state": update.previous_state,
    }


def _format_outcome_summary(summary: dict[str, int]) -> str:
    return "summary: " + " ".join(f"{key}={value}" for key, value in sorted(summary.items()))
