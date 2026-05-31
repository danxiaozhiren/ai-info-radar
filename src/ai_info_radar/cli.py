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
    _localize_argparse(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    poll_parser = subparsers.add_parser("poll", help="轮询已配置的 AI 情报来源。")
    _localize_argparse(poll_parser)
    poll_parser.add_argument("--manifest", required=True, help="来源清单 JSON 路径。")
    poll_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
    poll_parser.add_argument("--repo-root", default=".", help="用于解析相对夹具路径的仓库根目录。")
    poll_parser.add_argument("--timeout", type=float, default=10.0, help="抓取超时时间，单位秒。")
    poll_parser.add_argument("--json", action="store_true", help="输出机器可读的 JSON 摘要。")

    alert_parser = subparsers.add_parser("alert", help="发送一条强提醒到飞书。")
    _localize_argparse(alert_parser)
    alert_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
    alert_parser.add_argument(
        "--webhook-env",
        default="FEISHU_WEBHOOK_URL",
        help="保存飞书 Webhook URL 的环境变量名。",
    )
    alert_parser.add_argument("--timeout", type=float, default=10.0, help="Webhook 超时时间，单位秒。")
    alert_parser.add_argument("--rules", help="可选的 JSON 规则配置路径。")
    alert_parser.add_argument("--json", action="store_true", help="输出机器可读的 JSON 摘要。")

    daily_parser = subparsers.add_parser("daily", help="生成并可选发送晨间日报。")
    _localize_argparse(daily_parser)
    daily_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
    daily_parser.add_argument("--reports-dir", default="reports", help="Markdown 日报输出目录。")
    daily_parser.add_argument(
        "--webhook-env",
        default="FEISHU_WEBHOOK_URL",
        help="保存飞书 Webhook URL 的环境变量名。",
    )
    daily_parser.add_argument("--timeout", type=float, default=10.0, help="Webhook 超时时间，单位秒。")
    daily_parser.add_argument("--json", action="store_true", help="输出机器可读的 JSON 摘要。")

    items_parser = subparsers.add_parser("items", help="查看并更新已存条目的状态。")
    _localize_argparse(items_parser)
    item_subparsers = items_parser.add_subparsers(dest="items_command", required=True)

    list_parser = item_subparsers.add_parser("list", help="列出已存条目及其状态。")
    _localize_argparse(list_parser)
    list_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
    list_parser.add_argument(
        "--state",
        default="all",
        choices=["all", *sorted(ITEM_STATES)],
        help="按条目状态过滤。",
    )
    list_parser.add_argument("--json", action="store_true", help="输出机器可读的条目列表。")

    for command, target_state in (("read", "read"), ("save", "saved"), ("ignore", "ignored")):
        mark_parser = item_subparsers.add_parser(command, help=f"将条目标记为 {target_state}。")
        _localize_argparse(mark_parser)
        mark_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
        mark_parser.add_argument(
            "identifiers",
            nargs="+",
            help="'items list' 显示的条目 id 或指纹前缀。",
        )
        mark_parser.add_argument("--json", action="store_true", help="输出机器可读的更新摘要。")
        mark_parser.set_defaults(target_state=target_state)

    rule_test_parser = subparsers.add_parser("rule-test", help="预览规则结果，不产生副作用。")
    _localize_argparse(rule_test_parser)
    rule_test_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
    rule_test_parser.add_argument("--rules", help="可选的 JSON 规则配置路径。")
    rule_test_parser.add_argument("--limit", type=int, default=20, help="要检查的最近条目数量。")
    rule_test_parser.add_argument("--json", action="store_true", help="输出机器可读的规则报告。")

    reclassify_parser = subparsers.add_parser("reclassify", help="按当前规则重新计算条目状态。")
    _localize_argparse(reclassify_parser)
    reclassify_parser.add_argument("--db", required=True, help="本地 SQLite 数据库路径。")
    reclassify_parser.add_argument("--rules", help="可选的 JSON 规则配置路径。")
    reclassify_parser.add_argument("--limit", type=int, default=20, help="要重分类的最近条目数量。")
    reclassify_parser.add_argument(
        "--include-user-states",
        action="store_true",
        help="同时覆盖 read、saved、ignored 这些用户管理状态。",
    )
    reclassify_parser.add_argument("--json", action="store_true", help="输出机器可读的摘要。")

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
    parser.error(f"不支持的命令：{args.command}")
    return 2


def _localize_argparse(parser: argparse.ArgumentParser) -> None:
    parser._positionals.title = "位置参数"
    parser._optionals.title = "可选参数"
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            action.help = "显示帮助信息并退出。"


def _run_poll(args: argparse.Namespace) -> int:
    try:
        result = poll_sources(
            manifest_path=Path(args.manifest),
            db_path=Path(args.db),
            repo_root=Path(args.repo_root),
            timeout_seconds=args.timeout,
    )
    except ManifestError as exc:
        print(f"源清单错误：{exc}")
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
            f"轮询完成：新增={result.inserted} "
            f"已存在={result.existing} 失败={result.failures}"
        )
        for source_result in result.results:
            status = "成功" if source_result.ok else "失败"
            print(
                f"- {source_result.source_id}: {status}; "
                f"新增={source_result.inserted}; "
                f"已存在={source_result.existing}; {source_result.message}"
            )

    return 0


def _run_alert(args: argparse.Namespace) -> int:
    try:
        rules = load_rules(args.rules)
    except (RulesError, OSError, ValueError) as exc:
        print(f"规则错误：{exc}")
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
        print(f"提醒已发送：{result.short_id} {result.title}")
    elif result.status == "skipped":
        print(f"提醒已跳过：{result.message}")
    elif result.status == "blocked":
        print(f"提醒被阻止：{result.message}；请设置 {args.webhook_env}")
    else:
        print(f"提醒发送失败：{result.message}")

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
        print(f"日报已发送：{result.report_path}")
    elif result.status == "prepared":
        print(f"日报已生成：{result.report_path}；{result.message}")
    else:
        print(f"日报失败：{result.message}；报告={result.report_path}")

    return 0 if result.status in {"sent", "prepared"} else 1


def _run_items(args: argparse.Namespace) -> int:
    if args.items_command == "list":
        return _run_items_list(args)
    if args.items_command in {"read", "save", "ignore"}:
        return _run_items_mark(args)
    print(f"不支持的条目命令：{args.items_command}")
    return 2


def _run_items_list(args: argparse.Namespace) -> int:
    try:
        with RadarStore(Path(args.db)) as store:
            state = None if args.state == "all" else args.state
            items = store.list_items(state=state)
    except ItemStateError as exc:
        print(f"条目状态错误：{exc}")
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

    print(f"条目：数量={len(items)} 状态={args.state}")
    for item in items:
        print(
            f"- #{item.id} {item.fingerprint[:10]} 状态={item.state} "
            f"{item.title} ({item.source_name})"
        )
    return 0


def _run_items_mark(args: argparse.Namespace) -> int:
    try:
        with RadarStore(Path(args.db)) as store:
            updates = store.set_item_state_by_identifiers(args.identifiers, args.target_state)
    except ItemStateError as exc:
        print(f"条目状态错误：{exc}")
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
        f"条目已更新：状态={args.target_state} "
        f"已更新={len(updates)} 请求数={len(args.identifiers)}"
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
        print(f"规则错误：{exc}")
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

    print(f"规则测试：数量={len(items)}")
    print(_format_outcome_summary(summary))
    for item in items:
        stored = item.item
        print(
            f"- #{stored.id} {stored.fingerprint[:10]} 结果={item.outcome} "
            f"严重级别={item.decision.severity} 分数={item.decision.score} "
            f"状态={stored.state} {stored.title}"
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
        print(f"规则错误：{exc}")
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

    print(f"重分类完成：数量={len(updates)} 已变更={changed} 已保留={preserved}")
    print(_format_outcome_summary(summary))
    for update in updates:
        item = update.item
        print(
            f"- #{item.id} {item.fingerprint[:10]} {update.previous_state}->{update.new_state} "
            f"结果={update.outcome} 严重级别={update.decision.severity} {item.title}"
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
    return "汇总：" + " ".join(f"{key}={value}" for key, value in sorted(summary.items()))
