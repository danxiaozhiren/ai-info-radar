from __future__ import annotations

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
from ai_info_radar.digest import generate_daily_digest  # noqa: E402
from ai_info_radar.events import merge_events  # noqa: E402
from ai_info_radar.fingerprint import content_fingerprint  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult, AlertMessage, NormalizedItem  # noqa: E402
from ai_info_radar.notifiers import build_feishu_payload  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class EventMergeCooldownIssueTests(unittest.TestCase):
    def test_hard_deduplication_covers_url_feed_github_release_and_source_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Acme Agent v1.0.0 release",
                            url="https://github.com/acme/agent/releases/tag/v1.0.0?utm_source=news",
                            source_id="github-feed",
                            source_name="GitHub Feed",
                            authority_level="official_github",
                            trace={"feed_id": "feed-1", "source_item_id": "release-v1"},
                        ),
                        self._item(
                            title="Acme Agent v1.0.0 release notes",
                            url="https://github.com/acme/agent/releases/tag/v1.0.0",
                            source_id="github-release",
                            source_name="GitHub Release",
                            authority_level="official_github",
                        ),
                        self._item(
                            title="Acme Agent feed duplicate",
                            url="https://example.com/feed-copy",
                            source_id="github-feed",
                            source_name="GitHub Feed",
                            authority_level="official_github",
                            trace={"feed_id": "feed-1"},
                        ),
                        self._item(
                            title="Acme Agent source item duplicate",
                            url="https://example.com/source-copy",
                            source_id="github-feed",
                            source_name="GitHub Feed",
                            authority_level="official_github",
                            trace={"source_item_id": "release-v1"},
                        ),
                    ]
                )

                events = merge_events(store)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].item_count, 4)

    def test_approximate_deduplication_merges_similar_vendor_keyword_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Claude Code breaking change migrates hooks schema",
                            url="https://docs.example.com/claude-code/hooks",
                            summary="Breaking change for agent workflow configuration.",
                        ),
                        self._item(
                            title="Claude Code breaking change migration hooks schema",
                            url="https://docs.example.com/claude-code/hooks-v2",
                            summary="Migration warning for agent workflow setup.",
                        ),
                    ]
                )

                events = merge_events(store)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].item_count, 2)

    def test_aggregator_target_merges_into_existing_official_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
            self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")

            with RadarStore(db_path) as store:
                events = merge_events(store)
                items = {item.title: item for item in store.list_items()}
                official = items["Claude Code 1.2.0"]
                event_key = store.event_key_for_item(official.id)
                self.assertIsNotNone(event_key)
                supporting = store.event_supporting_sources(event_key or "", exclude_item_id=official.id)

            self.assertEqual(len(events), 3)
            self.assertEqual(supporting, ("agents-radar Daily Digest",))

    def test_alert_cooldown_sends_once_per_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            with RadarStore(db_path) as store:
                store.insert_items(
                    [
                        self._item(
                            title="Claude Code breaking change migrates hooks schema",
                            url="https://docs.example.com/claude-code/hooks",
                            summary="Breaking change for agent workflow configuration.",
                        ),
                        self._item(
                            title="Claude Code breaking change migration hooks schema",
                            url="https://docs.example.com/claude-code/hooks-v2",
                            summary="Migration warning for agent workflow setup.",
                        ),
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
            second = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )

            self.assertEqual(first.status, "sent")
            self.assertEqual(second.status, "skipped")
            self.assertEqual(len(deliveries), 1)
            with sqlite3.connect(db_path) as connection:
                alert_key = connection.execute("SELECT alert_key FROM alert_history").fetchone()[0]
            self.assertTrue(alert_key.startswith("event:"))

    def test_later_supporting_source_updates_existing_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            official = self._item(
                title="Claude Code 1.2.0",
                url="https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md#1-2-0",
                summary="Breaking change: migrated project settings to the new hooks schema.",
            )
            aggregator = self._item(
                title="Claude Code 1.2.0 breaking change",
                url="https://duanyytop.github.io/agents-radar/reports/2026-05-30.html#claude-code-1-2-0",
                source_id="agents-radar-daily",
                source_name="agents-radar Daily Digest",
                vendor="agents-radar",
                authority_level="aggregator",
                content_type="aggregator_candidate",
                summary="Aggregator note about the same migration.",
                trace={"target_url": official.url, "target_source": "Anthropic"},
            )
            with RadarStore(db_path) as store:
                store.insert_items([official])
                events = merge_events(store)
                self.assertEqual(events[0].item_count, 1)
                store.insert_items([aggregator])
                events = merge_events(store)
                official_item = store.list_items()[0]
                event_key = store.event_key_for_item(official_item.id)
                supporting = store.event_supporting_sources(event_key or "", exclude_item_id=official_item.id)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].item_count, 2)
            self.assertEqual(supporting, ("agents-radar Daily Digest",))

    def test_digest_shows_grouped_supporting_sources_for_alerted_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
            self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")
            with RadarStore(db_path) as store:
                merge_events(store)
                items = {item.title: item for item in store.list_items()}
                official = items["Claude Code 1.2.0"]
                event_key = store.event_key_for_item(official.id)
                store.record_alert(
                    alert_key=f"event:{event_key}",
                    item_id=official.id,
                    fingerprint=official.fingerprint,
                    notifier="feishu",
                    status="sent",
                    message='{"StatusCode":0}',
                )

            result = generate_daily_digest(
                db_path=db_path,
                reports_dir=Path(temp_dir) / "reports",
                report_date=date(2026, 5, 31),
            )

            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("supporting: agents-radar Daily Digest", report)

    def _item(
        self,
        *,
        title: str,
        url: str,
        source_id: str = "claude-code-changelog",
        source_name: str = "Claude Code Changelog",
        vendor: str = "Anthropic",
        authority_level: str = "official",
        content_type: str = "developer_changelog",
        summary: str = "Breaking change and migration for agent workflow.",
        trace: dict[str, str] | None = None,
    ) -> NormalizedItem:
        fingerprint = content_fingerprint(
            title=title,
            url=url,
            published_at="2026-05-31",
            summary=summary,
            vendor=vendor,
            content_type=content_type,
        )
        return NormalizedItem(
            source_id=source_id,
            source_name=source_name,
            vendor=vendor,
            authority_level=authority_level,
            content_type=content_type,
            title=title,
            url=url,
            detected_at="2026-05-31T08:00:00+00:00",
            published_at="2026-05-31",
            summary=summary,
            fingerprint=fingerprint,
            trace=trace or {},
        )

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


if __name__ == "__main__":
    unittest.main()
