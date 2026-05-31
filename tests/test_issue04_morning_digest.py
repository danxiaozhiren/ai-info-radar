from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.digest import generate_daily_digest  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult  # noqa: E402
from ai_info_radar.notifiers import build_feishu_text_payload  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class MorningDigestIssueTests(unittest.TestCase):
    def test_daily_digest_writes_markdown_with_required_groups_and_stats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "radar.sqlite"
            reports_dir = temp_path / "reports"
            self._seed_digest_db(db_path)

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=reports_dir,
                report_date=date(2026, 5, 30),
            )

            self.assertEqual(result.status, "prepared")
            self.assertFalse(result.sent)
            self.assertEqual(result.report_path, reports_dir / "ai-radar-digest-2026-05-30.md")
            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("# AI 情报雷达日报 - 2026-05-30", report)
            self.assertIn("## 已提醒", report)
            self.assertIn("Claude Code 1.2.0", report)
            self.assertIn("https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md#1-2-0", report)
            self.assertIn("## 值得阅读", report)
            self.assertIn("Claude Code 1.2.3", report)
            self.assertIn("## 已保存", report)
            self.assertIn("Context editing for long-running coding agents", report)
            self.assertIn("## 来源失败", report)
            self.assertIn("broken-official-source", report)
            self.assertIn("fixture unavailable", report)
            self.assertIn("## 过滤统计", report)
            self.assertIn("- 总条目数：4", report)
            self.assertIn("- 已提醒：1", report)
            self.assertIn("- 值得阅读：1", report)
            self.assertIn("- 已保存：1", report)
            self.assertIn("- 来源失败：1", report)
            self.assertIn("- 本次标记为已入日报：1", report)
            self.assertIn("已提醒=1", report)
            self.assertIn("已入日报=1", report)
            self.assertIn("已忽略=1", report)
            self.assertIn("已保存=1", report)
            self.assertNotIn("<html", report)
            self.assertNotIn("window.__docs_shell", report)

    def test_daily_digest_marks_only_new_included_items_daily(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._seed_digest_db(db_path)

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=Path(temp_dir) / "reports",
                report_date=date(2026, 5, 30),
            )

            self.assertEqual(result.marked_digested, 1)
            states = self._states_by_title(db_path)
            self.assertEqual(states["Claude Code 1.2.0"], "alerted")
            self.assertEqual(states["Claude Code 1.2.3"], "daily")
            self.assertEqual(states["Context editing for long-running coding agents"], "saved")
            self.assertEqual(
                states["Scaling Managed Agents: Decoupling the brain from the hands"],
                "ignored",
            )

    def test_daily_digest_filters_items_alerts_and_failures_to_report_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            reports_dir = Path(temp_dir) / "reports"
            self._seed_digest_db(db_path)

            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    UPDATE items
                    SET state = 'new', published_at = '2026-05-29'
                    WHERE title = ?
                    """,
                    ("Scaling Managed Agents: Decoupling the brain from the hands",),
                )
                connection.execute(
                    """
                    UPDATE items
                    SET state = 'new', published_at = '2026-05-30'
                    WHERE title = ?
                    """,
                    ("Context editing for long-running coding agents",),
                )
                connection.execute(
                    "UPDATE alert_history SET alerted_at = '2026-05-29T09:00:00+00:00'"
                )
                connection.execute(
                    """
                    UPDATE items
                    SET detected_at = '2026-05-29T09:00:00+00:00'
                    WHERE title = ?
                    """,
                    ("Claude Code 1.2.3",),
                )
                connection.execute(
                    "UPDATE source_health SET checked_at = '2026-05-29T09:00:00+00:00'"
                )
                connection.commit()

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=reports_dir,
                report_date=date(2026, 5, 30),
            )

            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("Context editing for long-running coding agents", report)
            self.assertNotIn("Scaling Managed Agents: Decoupling the brain from the hands", report)
            self.assertNotIn("Claude Code 1.2.0", report)
            self.assertNotIn("broken-official-source", report)
            self.assertEqual(result.marked_digested, 1)

    def test_initial_large_undated_source_backfill_is_not_reported_as_today(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "radar.sqlite"
            reports_dir = temp_path / "reports"
            changelog_path = temp_path / "large_changelog.md"
            manifest_path = temp_path / "sources.json"
            self._write_undated_changelog(changelog_path, range(12, 0, -1))
            self._write_changelog_manifest(manifest_path, changelog_path)

            first_poll = self._run_poll(db_path, manifest_path)

            self.assertIn("新增=12", first_poll.stdout)
            self.assertIn("已将 12 条无日期历史基线标记为已入日报", first_poll.stdout)
            with sqlite3.connect(db_path) as connection:
                baseline_states = connection.execute(
                    "SELECT state, COUNT(*) FROM items GROUP BY state"
                ).fetchall()
            self.assertEqual(baseline_states, [("daily", 12)])

            self._write_undated_changelog(changelog_path, range(13, 0, -1))
            second_poll = self._run_poll(db_path, manifest_path)
            with sqlite3.connect(db_path) as connection:
                connection.execute("UPDATE items SET detected_at = '2026-05-30T08:00:00+00:00'")
                connection.commit()

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=reports_dir,
                report_date=date(2026, 5, 30),
            )

            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("新增=1", second_poll.stdout)
            self.assertIn("Claude Code 2.0.13", report)
            self.assertNotIn("Claude Code 2.0.12", report)
            self.assertEqual(result.marked_digested, 1)

    def test_daily_digest_can_send_feishu_friendly_text_with_fake_sender(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._seed_digest_db(db_path)
            deliveries: list[tuple[str, str]] = []

            def fake_sender(webhook_url: str, text: str) -> AlertDeliveryResult:
                deliveries.append((webhook_url, text))
                return AlertDeliveryResult(
                    ok=True,
                    status_code=200,
                    message='{"StatusCode":0}',
                    payload=build_feishu_text_payload(text),
                )

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=Path(temp_dir) / "reports",
                webhook_url="https://open.feishu.example/webhook",
                report_date=date(2026, 5, 30),
                sender=fake_sender,
            )

            self.assertEqual(result.status, "sent")
            self.assertTrue(result.sent)
            self.assertEqual(len(deliveries), 1)
            webhook_url, text = deliveries[0]
            self.assertEqual(webhook_url, "https://open.feishu.example/webhook")
            self.assertIn("AI 情报雷达日报 - 2026-05-30", text)
            self.assertIn("已提醒：", text)
            self.assertIn("值得阅读：", text)
            self.assertIn("已保存：", text)
            self.assertIn("来源失败：", text)
            self.assertEqual(result.payload["msg_type"], "text")
            payload_text = result.payload["content"]["text"]  # type: ignore[index]
            self.assertEqual(payload_text, text)

    def test_daily_cli_writes_report_without_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "radar.sqlite"
            reports_dir = temp_path / "reports"
            self._seed_digest_db(db_path)

            env = {**os.environ, "PYTHONPATH": str(SRC)}
            env.pop("FEISHU_WEBHOOK_URL", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_info_radar",
                    "daily",
                    "--db",
                    str(db_path),
                    "--reports-dir",
                    str(reports_dir),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("日报已生成：", result.stdout)
            reports = list(reports_dir.glob("ai-radar-digest-*.md"))
            self.assertEqual(len(reports), 1)
            self.assertIn("AI 情报雷达日报", reports[0].read_text(encoding="utf-8"))

    def _seed_digest_db(self, db_path: Path) -> None:
        self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
        self._run_poll(db_path, ROOT / "configs" / "sources.anthropic.fixture.json")
        with RadarStore(db_path) as store:
            items = {item.title: item for item in store.list_items()}
            alerted = items["Claude Code 1.2.0"]
            store.record_alert(
                alert_key=f"item:{alerted.fingerprint}",
                item_id=alerted.id,
                fingerprint=alerted.fingerprint,
                notifier="feishu",
                status="sent",
                message='{"StatusCode":0}',
            )
            store.record_health(
                "broken-official-source",
                ok=False,
                message="fixture unavailable",
                item_count=0,
            )

        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "UPDATE items SET state = 'saved' WHERE title = ?",
                ("Context editing for long-running coding agents",),
            )
            connection.execute(
                "UPDATE items SET state = 'ignored' WHERE title = ?",
                ("Scaling Managed Agents: Decoupling the brain from the hands",),
            )
            connection.execute(
                """
                UPDATE items
                SET detected_at = '2026-05-30T08:00:00+00:00'
                WHERE source_name = 'Claude Code Changelog'
                """
            )
            connection.execute(
                "UPDATE alert_history SET alerted_at = '2026-05-30T08:05:00+00:00'"
            )
            connection.execute(
                """
                UPDATE source_health
                SET checked_at = '2026-05-30T08:10:00+00:00'
                WHERE source_id = 'broken-official-source'
                """
            )
            connection.commit()

    def _run_poll(self, db_path: Path, manifest_path: Path) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_info_radar",
                "poll",
                "--manifest",
                str(manifest_path),
                "--db",
                str(db_path),
                "--repo-root",
                str(ROOT),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def _write_undated_changelog(self, path: Path, versions: range) -> None:
        lines = ["# Changelog", ""]
        for version in versions:
            lines.extend(
                [
                    f"## 2.0.{version}",
                    "",
                    f"- Added release note {version} for agent workflow.",
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_changelog_manifest(self, path: Path, fixture_path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "id": "large-claude-code-changelog",
                            "name": "Large Claude Code Changelog",
                            "vendor": "Anthropic",
                            "source_type": "web_page",
                            "authority_level": "official",
                            "url": "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
                            "priority": 100,
                            "parsing_strategy": "claude_code_changelog",
                            "content_type": "developer_changelog",
                            "fixture_path": str(fixture_path),
                            "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    def _states_by_title(self, db_path: Path) -> dict[str, str]:
        with sqlite3.connect(db_path) as connection:
            rows = connection.execute("SELECT title, state FROM items").fetchall()
        return {title: state for title, state in rows}


if __name__ == "__main__":
    unittest.main()
