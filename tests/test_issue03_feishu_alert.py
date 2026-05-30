from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.alerts import send_next_critical_alert  # noqa: E402
from ai_info_radar.classifier import classify_item  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult, AlertMessage  # noqa: E402
from ai_info_radar.notifiers import build_feishu_payload, send_feishu_webhook  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class FeishuAlertIssueTests(unittest.TestCase):
    def test_classifier_detects_official_critical_changelog_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path)

            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}

            decision = classify_item(items["Claude Code 1.2.0"])

            self.assertTrue(decision.should_alert)
            self.assertEqual(decision.severity, "critical")
            self.assertIn("official authority: official", decision.reasons)
            self.assertIn("high-signal content type: developer_changelog", decision.reasons)
            for term in ["breaking change", "migrated", "deprecated", "agent workflow"]:
                self.assertIn(term, decision.matched_terms)

    def test_alert_service_sends_once_and_records_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path)
            self._keep_only_title(db_path, "Claude Code 1.2.0")
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
            second = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )

            self.assertEqual(first.status, "sent")
            self.assertTrue(first.sent)
            self.assertEqual(first.title, "Claude Code 1.2.0")
            self.assertEqual(second.status, "skipped")
            self.assertEqual(second.message, "no unalerted critical item")
            self.assertEqual(len(deliveries), 1)
            self.assertTrue(deliveries[0].short_id)
            self.assertEqual(deliveries[0].source, "Claude Code Changelog (Anthropic)")
            self.assertEqual(deliveries[0].authority, "official")
            self.assertIn("breaking change", deliveries[0].why_it_matters)
            self.assertTrue(deliveries[0].original_link.endswith("#v1-2-0"))

            with sqlite3.connect(db_path) as connection:
                rows = connection.execute(
                    "SELECT alert_key, notifier, status FROM alert_history"
                ).fetchall()

            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0][0].startswith("item:"))
            self.assertEqual(rows[0][1], "feishu")
            self.assertEqual(rows[0][2], "sent")

    def test_notifier_builds_payload_without_deciding_classification(self) -> None:
        message = AlertMessage(
            short_id="abc123def0",
            title="Claude Code 1.2.0",
            source="Claude Code Changelog (Anthropic)",
            authority="official",
            why_it_matters="official authority: official; breaking change",
            original_link="https://docs.anthropic.com/en/release-notes/claude-code#v1-2-0",
            supporting_sources=("Anthropic Engineering",),
            matched_terms=("breaking change", "deprecated"),
        )

        payload = build_feishu_payload(message)

        self.assertEqual(payload["msg_type"], "text")
        text = payload["content"]["text"]  # type: ignore[index]
        self.assertIn("[abc123def0] Claude Code 1.2.0", text)
        self.assertIn("Source: Claude Code Changelog (Anthropic)", text)
        self.assertIn("Authority: official", text)
        self.assertIn("Why: official authority: official; breaking change", text)
        self.assertIn("Link: https://docs.anthropic.com", text)
        self.assertIn("Supporting sources: Anthropic Engineering", text)
        self.assertIn("Matched terms: breaking change, deprecated", text)

    def test_feishu_sender_accepts_fake_transport_for_networkless_tests(self) -> None:
        message = AlertMessage(
            short_id="abc123def0",
            title="Claude Code 1.2.0",
            source="Claude Code Changelog (Anthropic)",
            authority="official",
            why_it_matters="breaking change",
            original_link="https://docs.anthropic.com/en/release-notes/claude-code#v1-2-0",
        )
        captured: dict[str, object] = {}

        class FakeResponse:
            status = 200

            def read(self) -> bytes:
                return b'{"StatusCode":0}'

        def fake_opener(req: request.Request, timeout: float) -> FakeResponse:
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["data"] = json.loads(req.data.decode("utf-8"))  # type: ignore[union-attr]
            return FakeResponse()

        result = send_feishu_webhook(
            "https://open.feishu.example/webhook",
            message,
            timeout_seconds=2.5,
            opener=fake_opener,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(captured["url"], "https://open.feishu.example/webhook")
        self.assertEqual(captured["timeout"], 2.5)
        self.assertEqual(captured["data"], build_feishu_payload(message))

    def test_alert_cli_blocks_when_webhook_env_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path)

            result = self._run_alert(db_path, env_overrides={"FEISHU_WEBHOOK_URL": None})

            self.assertEqual(result.returncode, 1)
            self.assertIn("alert blocked: missing FEISHU_WEBHOOK_URL", result.stdout)
            self.assertIn("set FEISHU_WEBHOOK_URL", result.stdout)

    def test_alert_cli_skips_when_no_critical_items_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path):
                pass

            result = self._run_alert(db_path, env_overrides={"FEISHU_WEBHOOK_URL": None})

            self.assertEqual(result.returncode, 0)
            self.assertIn("alert skipped: no unalerted critical item", result.stdout)

    def _run_poll(self, db_path: Path) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_info_radar",
                "poll",
                "--manifest",
                str(ROOT / "configs" / "sources.claude-code.fixture.json"),
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

    def _run_alert(
        self,
        db_path: Path,
        *,
        env_overrides: dict[str, str | None] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        for key, value in (env_overrides or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_info_radar",
                "alert",
                "--db",
                str(db_path),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _keep_only_title(self, db_path: Path, title: str) -> None:
        with sqlite3.connect(db_path) as connection:
            connection.execute("DELETE FROM items WHERE title != ?", (title,))
            connection.commit()


if __name__ == "__main__":
    unittest.main()
