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

from ai_info_radar.alerts import send_next_critical_alert  # noqa: E402
from ai_info_radar.classifier import classify_item  # noqa: E402
from ai_info_radar.digest import generate_daily_digest  # noqa: E402
from ai_info_radar.extractors import extract_statuspage_incidents  # noqa: E402
from ai_info_radar.fetchers import fetch_source  # noqa: E402
from ai_info_radar.manifest import load_sources  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult, AlertMessage  # noqa: E402
from ai_info_radar.notifiers import build_feishu_payload  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class StatusIncidentIssueTests(unittest.TestCase):
    def test_manifest_loads_official_status_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.anthropic-status.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "anthropic-status-incidents")
        self.assertEqual(source.source_type, "status_api")
        self.assertEqual(source.authority_level, "status")
        self.assertEqual(source.parsing_strategy, "statuspage_incidents")
        self.assertEqual(source.content_type, "status_incident")

    def test_status_extractor_normalizes_incident_and_recovery_records(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.anthropic-status.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_statuspage_incidents(fetched)

        self.assertEqual(len(items), 2)
        incident = items[0]
        recovery = items[1]
        self.assertEqual(incident.title, "Status investigating: Elevated errors for Claude API requests")
        self.assertEqual(
            incident.url,
            "https://status.anthropic.com/incidents/inc-api-20260531",
        )
        self.assertEqual(incident.published_at, "2026-05-31T00:15:00.000Z")
        self.assertEqual(incident.authority_level, "status")
        self.assertEqual(incident.content_type, "status_incident")
        self.assertIn("Status: investigating", incident.summary)
        self.assertIn("Impact: major", incident.summary)
        self.assertIn("elevated errors", incident.summary)
        self.assertIn("Claude API (partial_outage)", incident.summary)
        self.assertEqual(incident.trace["source_item_id"], "inc-api-20260531")
        self.assertEqual(incident.trace["statuspage_status"], "investigating")
        self.assertEqual(incident.trace["impact"], "major")

        self.assertEqual(recovery.title, "Status resolved: Claude Console login failures")
        self.assertIn("resolved", recovery.summary)
        self.assertIn("recovered", recovery.summary)
        self.assertEqual(recovery.trace["resolved_at"], "2026-05-30T20:40:00.000Z")

    def test_status_incident_and_recovery_classify_as_critical_official_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.anthropic-status.fixture.json")

            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}

            incident_decision = classify_item(
                items["Status investigating: Elevated errors for Claude API requests"]
            )
            recovery_decision = classify_item(
                items["Status resolved: Claude Console login failures"]
            )

            self.assertTrue(incident_decision.should_alert)
            self.assertEqual(incident_decision.severity, "critical")
            self.assertIn("official authority: status", incident_decision.reasons)
            self.assertIn("high-signal content type: status_incident", incident_decision.reasons)
            self.assertIn("investigating", incident_decision.matched_terms)
            self.assertIn("elevated errors", incident_decision.matched_terms)
            self.assertIn("degraded", incident_decision.matched_terms)

            self.assertTrue(recovery_decision.should_alert)
            self.assertEqual(recovery_decision.severity, "critical")
            self.assertIn("resolved", recovery_decision.matched_terms)
            self.assertIn("recovered", recovery_decision.matched_terms)

    def test_status_alert_sends_once_for_repeated_polling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            first_poll = self._run_poll(db_path, ROOT / "configs" / "sources.anthropic-status.fixture.json")
            second_poll = self._run_poll(db_path, ROOT / "configs" / "sources.anthropic-status.fixture.json")
            deliveries: list[AlertMessage] = []

            def fake_sender(webhook_url: str, message: AlertMessage) -> AlertDeliveryResult:
                deliveries.append(message)
                return AlertDeliveryResult(
                    ok=True,
                    status_code=200,
                    message='{"StatusCode":0}',
                    payload=build_feishu_payload(message),
                )

            first_alert = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )
            second_alert = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )
            third_alert = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )

            self.assertIn("新增=2", first_poll.stdout)
            self.assertIn("已存在=2", second_poll.stdout)
            self.assertEqual(first_alert.status, "sent")
            self.assertEqual(second_alert.status, "sent")
            self.assertEqual(third_alert.status, "skipped")
            self.assertEqual(len(deliveries), 2)
            self.assertEqual(deliveries[0].source, "Anthropic Status Incidents (Anthropic)")
            self.assertEqual(deliveries[0].authority, "status")
            self.assertIn("Status investigating", deliveries[0].title)

    def test_source_failure_is_recorded_for_digest_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "radar.sqlite"
            manifest_path = temp_path / "sources.json"
            manifest = json.loads(
                (ROOT / "configs" / "sources.anthropic-status.fixture.json").read_text(encoding="utf-8")
            )
            manifest["sources"][0]["fixture_path"] = "tests/fixtures/missing_status.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            poll = self._run_poll(db_path, manifest_path)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    UPDATE source_health
                    SET checked_at = '2026-05-31T08:10:00+00:00'
                    WHERE source_id = 'anthropic-status-incidents'
                    """
                )
                connection.commit()
            digest = generate_daily_digest(
                db_path=db_path,
                reports_dir=temp_path / "reports",
                report_date=date(2026, 5, 31),
            )

            self.assertIn("失败=1", poll.stdout)
            report = digest.report_path.read_text(encoding="utf-8")
            self.assertIn("## 来源失败", report)
            self.assertIn("anthropic-status-incidents", report)
            self.assertIn("无法读取", report)

    def test_empty_status_incident_feed_is_ok_and_records_zero_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fixture_path = temp_path / "empty_status.json"
            fixture_path.write_text(json.dumps({"incidents": []}), encoding="utf-8")
            manifest_path = temp_path / "sources.json"
            manifest = json.loads(
                (ROOT / "configs" / "sources.anthropic-status.fixture.json").read_text(encoding="utf-8")
            )
            manifest["sources"][0]["fixture_path"] = str(fixture_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self._run_poll(db_path=temp_path / "radar.sqlite", manifest_path=manifest_path, repo_root=Path("/"))

            self.assertIn("新增=0", result.stdout)
            self.assertIn("失败=0", result.stdout)
            self.assertIn("提取到 0 条", result.stdout)

    def _run_poll(
        self,
        db_path: Path,
        manifest_path: Path,
        *,
        repo_root: Path = ROOT,
    ) -> subprocess.CompletedProcess[str]:
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
                str(repo_root),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result


if __name__ == "__main__":
    unittest.main()
