from __future__ import annotations

from datetime import datetime
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_info_radar.config import load_focus, load_sources  # noqa: E402
from ai_info_radar.models import RadarItem  # noqa: E402
from ai_info_radar.pipeline import (  # noqa: E402
    cluster_similar_items,
    filter_by_max_age,
    run_daily_radar,
    select_ranked_items,
    write_daily_radar,
)


class PipelineTests(unittest.TestCase):
    def test_loads_yaml_subset_configs(self) -> None:
        focus = load_focus(ROOT / "configs" / "focus.example.yaml")
        sources = load_sources(ROOT / "configs" / "sources.local.yaml")

        self.assertEqual(focus.name, "Browser Use / AI Agent")
        self.assertIn("browser use", focus.keywords)
        self.assertEqual(sources[0].type, "local_json")

    def test_primary_sources_config_is_machine_readable_and_bounded(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.primary.yaml")

        self.assertGreaterEqual(len(sources), 8)
        self.assertTrue(all(source.enabled for source in sources))
        self.assertTrue(all(source.type == "rss" for source in sources))
        self.assertTrue(all(source.tier == "primary" for source in sources))
        self.assertTrue(all(source.limit is not None for source in sources))

    def test_runs_daily_radar_from_local_sample(self) -> None:
        run = run_daily_radar(
            sources_path=ROOT / "configs" / "sources.local.yaml",
            focus_path=ROOT / "configs" / "focus.example.yaml",
            scoring_path=ROOT / "configs" / "scoring.example.yaml",
            repo_root=ROOT,
        )

        self.assertGreaterEqual(len(run.items), 5)
        self.assertFalse(run.fetch_errors)
        self.assertGreaterEqual(run.items[0].final_score, run.items[-1].final_score)
        self.assertTrue(any("browser use" in item.related_focus_topics for item in run.items))

    def test_writes_markdown_report(self) -> None:
        run = run_daily_radar(
            sources_path=ROOT / "configs" / "sources.local.yaml",
            focus_path=ROOT / "configs" / "focus.example.yaml",
            scoring_path=ROOT / "configs" / "scoring.example.yaml",
            repo_root=ROOT,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "daily-radar.md"
            report = write_daily_radar(run, output)

            self.assertTrue(output.exists())
            self.assertIn("# AI 每日雷达", report)
            self.assertIn("Asia/Shanghai", report)
            self.assertIn("## 行动建议", report)
            self.assertIn("- 日期：发布/更新", report)
            self.assertIn("- 中文要点：", report)
            self.assertIn("- 原文证据：", report)
            self.assertIn("- 为什么重要：", report)

    def test_can_write_english_report(self) -> None:
        run = run_daily_radar(
            sources_path=ROOT / "configs" / "sources.local.yaml",
            focus_path=ROOT / "configs" / "focus.example.yaml",
            scoring_path=ROOT / "configs" / "scoring.example.yaml",
            repo_root=ROOT,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "daily-radar.md"
            report = write_daily_radar(run, output, language="en")

            self.assertTrue(output.exists())
            self.assertIn("# AI Daily Radar", report)
            self.assertIn("## Actions", report)

    def test_can_cap_ranked_items_per_source(self) -> None:
        ranked = [
            RadarItem(
                title=f"item {index}",
                url=f"https://example.com/{index}",
                source_name="same source",
                source_tier="primary",
                source_type="local_json",
                fetched_time="2026-05-18T00:00:00+00:00",
                final_score=10 - index,
            )
            for index in range(5)
        ]

        selected = select_ranked_items(ranked, max_items=10, max_per_source=2)

        self.assertEqual(len(selected), 2)
        self.assertEqual([item.title for item in selected], ["item 0", "item 1"])

    def test_can_filter_stale_items_by_date(self) -> None:
        items = [
            RadarItem(
                title="fresh",
                url="https://example.com/fresh",
                source_name="source",
                source_tier="primary",
                source_type="local_json",
                fetched_time="2026-05-18T00:00:00+00:00",
                published_time="2026-05-17",
            ),
            RadarItem(
                title="stale",
                url="https://example.com/stale",
                source_name="source",
                source_tier="primary",
                source_type="local_json",
                fetched_time="2026-05-18T00:00:00+00:00",
                published_time="2026-03-01",
            ),
        ]

        selected = filter_by_max_age(
            items,
            max_age_days=30,
            now=datetime.fromisoformat("2026-05-18T00:00:00+00:00"),
        )

        self.assertEqual([item.title for item in selected], ["fresh"])

    def test_can_cluster_similar_release_items(self) -> None:
        items = [
            RadarItem(
                title="v0.17.1",
                url="https://example.com/1",
                source_name="OpenAI Agents Python Releases",
                source_tier="primary",
                source_type="rss",
                fetched_time="2026-05-18T00:00:00+00:00",
                summary="sandbox fixes and MCP updates",
                final_score=9,
            ),
            RadarItem(
                title="v0.17.0",
                url="https://example.com/2",
                source_name="OpenAI Agents Python Releases",
                source_tier="primary",
                source_type="rss",
                fetched_time="2026-05-18T00:00:00+00:00",
                summary="sandbox migration note",
                final_score=8,
            ),
        ]

        clustered = cluster_similar_items(items)

        self.assertEqual(len(clustered), 1)
        self.assertEqual(clustered[0].title, "v0.17.1")
        self.assertEqual([item.title for item in clustered[0].related_items], ["v0.17.0"])


if __name__ == "__main__":
    unittest.main()
