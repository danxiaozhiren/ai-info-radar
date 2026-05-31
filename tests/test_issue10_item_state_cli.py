from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.alerts import send_next_critical_alert  # noqa: E402
from ai_info_radar.digest import generate_daily_digest  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult, AlertMessage  # noqa: E402
from ai_info_radar.notifiers import build_feishu_payload  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class ItemStateCliIssueTests(unittest.TestCase):
    def test_cli_marks_items_by_numeric_id_and_fingerprint_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._seed_items(db_path)
            with RadarStore(db_path) as store:
                items = store.list_items()

            result = self._run_cli(
                [
                    "items",
                    "save",
                    "--db",
                    str(db_path),
                    str(items[0].id),
                    items[1].fingerprint[:10],
                    "--json",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "saved")
            self.assertEqual(payload["requested"], 2)
            self.assertEqual(payload["updated"], 2)
            with RadarStore(db_path) as store:
                saved = store.list_items(state="saved")
            self.assertEqual([item.id for item in saved], [items[0].id, items[1].id])

    def test_cli_read_save_ignore_states_persist_and_can_be_listed_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._seed_items(db_path)
            with RadarStore(db_path) as store:
                items = store.list_items()

            self.assertEqual(
                self._run_cli(["items", "read", "--db", str(db_path), str(items[0].id)]).returncode,
                0,
            )
            self.assertEqual(
                self._run_cli(["items", "save", "--db", str(db_path), str(items[1].id)]).returncode,
                0,
            )
            self.assertEqual(
                self._run_cli(["items", "ignore", "--db", str(db_path), str(items[2].id)]).returncode,
                0,
            )

            listed = self._run_cli(["items", "list", "--db", str(db_path), "--state", "ignored", "--json"])

            self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
            payload = json.loads(listed.stdout)
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["items"][0]["id"], items[2].id)
            with RadarStore(db_path) as store:
                states = {item.id: item.state for item in store.list_items()}
            self.assertEqual(states[items[0].id], "read")
            self.assertEqual(states[items[1].id], "saved")
            self.assertEqual(states[items[2].id], "ignored")

    def test_saved_read_and_ignored_items_are_filtered_in_daily_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            reports_dir = Path(temp_dir) / "reports"
            self._seed_items(db_path)
            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}
                store.set_item_state_by_identifiers(
                    [str(items["Context editing for long-running coding agents"].id)],
                    "saved",
                )
                store.set_item_state_by_identifiers(
                    [str(items["Scaling Managed Agents: Decoupling the brain from the hands"].id)],
                    "ignored",
                )
                store.set_item_state_by_identifiers(
                    [str(items["Claude Code 1.2.3"].id)],
                    "read",
                )

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=reports_dir,
                report_date=date(2026, 5, 31),
            )

            report = result.report_path.read_text(encoding="utf-8")
            self.assertEqual(result.marked_digested, 1)
            self.assertIn("## Saved", report)
            self.assertIn("Context editing for long-running coding agents", report)
            self.assertNotIn("Scaling Managed Agents: Decoupling the brain from the hands", report)
            self.assertNotIn("Claude Code 1.2.3", report)
            self.assertIn("daily=1", report)
            self.assertIn("ignored=1", report)
            self.assertIn("read=1", report)
            self.assertIn("saved=1", report)

    def test_ignored_critical_items_are_not_alerted_but_can_be_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}
                critical = items["Claude Code 1.2.0"]
                store.set_item_state_by_identifiers([str(critical.id)], "ignored")
                for item in items.values():
                    if item.id != critical.id:
                        store.set_item_state_by_identifiers([str(item.id)], "read")
            deliveries: list[AlertMessage] = []

            def fake_sender(webhook_url: str, message: AlertMessage) -> AlertDeliveryResult:
                deliveries.append(message)
                return AlertDeliveryResult(
                    ok=True,
                    status_code=200,
                    message='{"StatusCode":0}',
                    payload=build_feishu_payload(message),
                )

            alert = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )
            ignored = self._run_cli(["items", "list", "--db", str(db_path), "--state", "ignored"])

            self.assertEqual(alert.status, "skipped")
            self.assertEqual(deliveries, [])
            self.assertIn("Claude Code 1.2.0", ignored.stdout)

    def test_cli_rejects_unknown_item_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._seed_items(db_path)

            result = self._run_cli(["items", "ignore", "--db", str(db_path), "does-not-exist"])

            self.assertEqual(result.returncode, 2)
            self.assertIn("item state error: Unknown item identifier: does-not-exist", result.stdout)

    def _seed_items(self, db_path: Path) -> None:
        self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
        self._run_poll(db_path, ROOT / "configs" / "sources.anthropic.fixture.json")

    def _run_poll(self, db_path: Path, manifest_path: Path) -> subprocess.CompletedProcess[str]:
        return self._run_cli(
            [
                "poll",
                "--manifest",
                str(manifest_path),
                "--db",
                str(db_path),
                "--repo-root",
                str(ROOT),
            ]
        )

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        result = subprocess.run(
            [sys.executable, "-m", "ai_info_radar", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if args[0] == "poll":
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result


if __name__ == "__main__":
    unittest.main()
