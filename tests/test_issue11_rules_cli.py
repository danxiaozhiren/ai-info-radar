from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.alerts import send_next_critical_alert  # noqa: E402
from ai_info_radar.fingerprint import content_fingerprint  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult, AlertMessage, NormalizedItem  # noqa: E402
from ai_info_radar.notifiers import build_feishu_payload  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class RulesCliIssueTests(unittest.TestCase):
    def test_rule_config_can_be_changed_without_code_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "radar.sqlite"
            rules_path = temp_path / "rules.json"
            self._write_custom_rules(rules_path, term="protocol handshake")
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Official protocol handshake update",
                            summary="Small protocol handshake update for agent clients.",
                        )
                    ]
                )

            result = self._run_cli(
                [
                    "rule-test",
                    "--db",
                    str(db_path),
                    "--rules",
                    str(rules_path),
                    "--json",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["items"][0]["outcome"], "would-alert")
            self.assertIn("protocol handshake", payload["items"][0]["matched_terms"])

    def test_rule_test_reports_all_outcomes_without_mutating_alert_history_or_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Claude Code breaking change migrates hooks",
                            summary="Breaking change for migrated agent workflow hooks.",
                        ),
                        self._item(
                            title="Official weekly roundup",
                            content_type="news",
                            summary="Interesting but not urgent.",
                        ),
                        self._item(
                            title="Aggregator MCP permissions",
                            authority_level="aggregator",
                            content_type="aggregator_candidate",
                            summary="MCP permission change spotted in a community digest.",
                        ),
                        self._item(
                            title="Social rumor",
                            authority_level="social",
                            content_type="news",
                            summary="Loose chatter without an official target.",
                        ),
                    ]
                )
            before_states = self._states_by_title(db_path)

            result = self._run_cli(["rule-test", "--db", str(db_path), "--json"])

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["would-alert"], 1)
            self.assertEqual(payload["summary"]["would-digest"], 1)
            self.assertEqual(payload["summary"]["candidate"], 1)
            self.assertEqual(payload["summary"]["ignored"], 1)
            self.assertEqual(self._alert_history_count(db_path), 0)
            self.assertEqual(self._states_by_title(db_path), before_states)

    def test_reclassify_recomputes_recent_item_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Claude Code breaking change migrates hooks",
                            summary="Breaking change for migrated agent workflow hooks.",
                        ),
                        self._item(
                            title="Social rumor",
                            authority_level="social",
                            content_type="news",
                            summary="Loose chatter without an official target.",
                        ),
                    ]
                )
                items = {item.title: item for item in store.list_items()}
                store.set_item_state_by_id(items["Claude Code breaking change migrates hooks"].id, "daily")

            result = self._run_cli(["reclassify", "--db", str(db_path), "--json"])

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["changed"], 2)
            states = self._states_by_title(db_path)
            self.assertEqual(states["Claude Code breaking change migrates hooks"], "new")
            self.assertEqual(states["Social rumor"], "ignored")

    def test_reclassify_does_not_make_previously_alerted_items_resend_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Claude Code breaking change migrates hooks",
                            summary="Breaking change for migrated agent workflow hooks.",
                        )
                    ]
                )
            deliveries: list[AlertMessage] = []

            def fake_sender(webhook_url: str, message: AlertMessage) -> AlertDeliveryResult:
                deliveries.append(message)
                return AlertDeliveryResult(
                    ok=True,
                    status_code=200,
                    message='{"StatusCode":0}',
                    payload=build_feishu_payload(message),
                )

            first = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )
            with RadarStore(db_path) as store:
                item = store.list_items()[0]
                store.set_item_state_by_id(item.id, "daily")

            result = self._run_cli(["reclassify", "--db", str(db_path), "--json"])
            second = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )

            self.assertEqual(first.status, "sent")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(second.status, "skipped")
            self.assertEqual(len(deliveries), 1)
            self.assertEqual(self._states_by_title(db_path)["Claude Code breaking change migrates hooks"], "alerted")

    def _item(
        self,
        *,
        title: str,
        summary: str,
        authority_level: str = "official",
        content_type: str = "developer_changelog",
    ) -> NormalizedItem:
        fingerprint = content_fingerprint(
            title=title,
            url=f"https://example.com/{title.lower().replace(' ', '-')}",
            published_at="2026-05-31",
            summary=summary,
            vendor="Example",
            content_type=content_type,
        )
        return NormalizedItem(
            source_id=f"{authority_level}-fixture",
            source_name=f"{authority_level.title()} Fixture",
            vendor="Example",
            authority_level=authority_level,
            content_type=content_type,
            title=title,
            url=f"https://example.com/{fingerprint[:12]}",
            detected_at="2026-05-31T08:00:00+00:00",
            published_at="2026-05-31",
            summary=summary,
            fingerprint=fingerprint,
            trace={},
        )

    def _write_custom_rules(self, path: Path, *, term: str) -> None:
        rules = json.loads((ROOT / "configs" / "rules.default.json").read_text(encoding="utf-8"))
        rules["keyword_rules"].append(
            {
                "name": "custom_rule",
                "terms": [term],
                "score": 99,
                "reason": "custom rule",
            }
        )
        path.write_text(json.dumps(rules), encoding="utf-8")

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        return subprocess.run(
            [sys.executable, "-m", "ai_info_radar", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _states_by_title(self, db_path: Path) -> dict[str, str]:
        with sqlite3.connect(db_path) as connection:
            rows = connection.execute("SELECT title, state FROM items").fetchall()
        return {title: state for title, state in rows}

    def _alert_history_count(self, db_path: Path) -> int:
        with sqlite3.connect(db_path) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM alert_history").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
