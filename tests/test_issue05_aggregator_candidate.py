from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.alerts import send_next_critical_alert  # noqa: E402
from ai_info_radar.classifier import classify_item  # noqa: E402
from ai_info_radar.extractors import extract_agents_radar_digest  # noqa: E402
from ai_info_radar.manifest import load_sources  # noqa: E402
from ai_info_radar.models import AlertDeliveryResult, AlertMessage  # noqa: E402
from ai_info_radar.notifiers import build_feishu_payload  # noqa: E402
from ai_info_radar.fetchers import fetch_source  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class AggregatorCandidateIssueTests(unittest.TestCase):
    def test_manifest_loads_agents_radar_as_non_official_manual_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.agents-radar.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "agents-radar-daily")
        self.assertEqual(source.authority_level, "aggregator")
        self.assertNotIn(source.authority_level, {"official", "official_github", "status"})
        self.assertEqual(source.parsing_strategy, "agents_radar_digest")
        self.assertEqual(source.content_type, "aggregator_candidate")

        claude_sources = load_sources(ROOT / "configs" / "sources.claude-code.fixture.json")
        self.assertEqual([item.id for item in claude_sources], ["claude-code-changelog"])

    def test_extractor_stores_aggregator_link_and_target_link_in_trace(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.agents-radar.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_agents_radar_digest(fetched)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Claude Code 1.2.0 breaking change")
        self.assertEqual(
            items[0].url,
            "https://duanyytop.github.io/agents-radar/reports/2026-05-30.html#claude-code-1-2-0",
        )
        self.assertEqual(items[0].authority_level, "aggregator")
        self.assertEqual(items[0].content_type, "aggregator_candidate")
        self.assertEqual(
            items[0].trace["target_url"],
            "https://docs.anthropic.com/en/release-notes/claude-code#v1-2-0",
        )
        self.assertEqual(items[0].trace["target_source"], "Anthropic")
        self.assertIn("deprecated legacy slash-command", items[0].summary)
        self.assertEqual(
            items[1].trace["target_url"],
            "https://github.com/example/mcp-toolkit/releases/tag/v2.0.0",
        )
        self.assertEqual(items[1].trace["target_source"], "GitHub")

    def test_aggregator_only_critical_language_is_candidate_not_strong_alert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")

            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}

            decision = classify_item(
                items["Open-source MCP toolkit adds agent workflow permissions"]
            )

            self.assertFalse(decision.should_alert)
            self.assertEqual(decision.severity, "candidate")
            self.assertIn("candidate authority: aggregator", decision.reasons)
            self.assertIn("mcp", decision.matched_terms)
            self.assertIn("permission", decision.matched_terms)

    def test_aggregator_target_can_support_existing_official_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
            self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")

            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}
                official = items["Claude Code 1.2.0"]
                supporting_sources = store.supporting_sources_for(
                    title=official.title,
                    target_url=official.url,
                    exclude_item_id=official.id,
                )

            self.assertEqual(supporting_sources, ("agents-radar Daily Digest",))

    def test_official_alert_includes_aggregator_supporting_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path, ROOT / "configs" / "sources.claude-code.fixture.json")
            self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")
            deliveries: list[AlertMessage] = []

            def fake_sender(webhook_url: str, message: AlertMessage) -> AlertDeliveryResult:
                deliveries.append(message)
                return AlertDeliveryResult(
                    ok=True,
                    status_code=200,
                    message='{"StatusCode":0}',
                    payload=build_feishu_payload(message),
                )

            result = send_next_critical_alert(
                db_path=db_path,
                webhook_url="https://open.feishu.example/webhook",
                sender=fake_sender,
            )

            self.assertEqual(result.status, "sent")
            self.assertEqual(result.title, "Claude Code 1.2.0")
            self.assertEqual(deliveries[0].supporting_sources, ("agents-radar Daily Digest",))

    def test_poll_cli_persists_aggregator_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"

            first = self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")
            second = self._run_poll(db_path, ROOT / "configs" / "sources.agents-radar.fixture.json")

            self.assertIn("inserted=2", first.stdout)
            self.assertIn("existing=0", first.stdout)
            self.assertIn("inserted=0", second.stdout)
            self.assertIn("existing=2", second.stdout)

            with RadarStore(db_path) as store:
                items = store.list_items()

            self.assertEqual(len(items), 2)
            self.assertTrue(all(item.authority_level == "aggregator" for item in items))
            self.assertTrue(all(item.trace.get("target_url") for item in items))

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
