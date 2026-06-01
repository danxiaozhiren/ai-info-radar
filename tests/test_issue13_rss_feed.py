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

from ai_info_radar.extractors import extract_items, extract_rss_feed  # noqa: E402
from ai_info_radar.fetchers import fetch_source  # noqa: E402
from ai_info_radar.manifest import load_sources  # noqa: E402


class RssFeedParserTests(unittest.TestCase):
    def test_manifest_loads_google_ai_blog_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.google-ai-blog.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "google-ai-blog")
        self.assertEqual(source.vendor, "Google DeepMind")
        self.assertEqual(source.authority_level, "official")
        self.assertEqual(source.parsing_strategy, "rss_feed")
        self.assertEqual(source.content_type, "engineering")
        self.assertEqual(source.source_type, "rss")

    def test_manifest_loads_qwen_blog_atom_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.qwen-blog.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "qwen-blog")
        self.assertEqual(source.vendor, "Qwen")
        self.assertEqual(source.parsing_strategy, "rss_feed")
        self.assertEqual(source.source_type, "atom")

    def test_extraction_normalizes_rss_20_items(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.google-ai-blog.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_rss_feed(fetched)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].title, "Gemini 3.5: frontier intelligence with action")
        self.assertEqual(
            items[0].url,
            "https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5/",
        )
        self.assertEqual(items[0].published_at, "Wed, 21 May 2026 16:00:00 GMT")
        self.assertEqual(items[0].vendor, "Google DeepMind")
        self.assertEqual(items[0].content_type, "engineering")
        self.assertEqual(items[0].authority_level, "official")
        self.assertEqual(items[0].trace["parser"], "rss_feed")
        self.assertEqual(items[0].trace["feed_format"], "rss")
        self.assertIn("today we're introducing gemini 3.5", items[0].summary.lower())

    def test_extraction_normalizes_atom_items(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.qwen-blog.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_rss_feed(fetched)

        self.assertEqual(len(items), 3)
        self.assertEqual(
            items[0].title, "Qwen3Guard: Real-time Safety for Your Token Stream"
        )
        self.assertEqual(
            items[0].url, "https://qwenlm.github.io/blog/qwen3guard/"
        )
        self.assertEqual(items[0].published_at, "2025-08-19T01:30:00+08:00")
        self.assertEqual(items[0].vendor, "Qwen")
        self.assertEqual(items[0].trace["parser"], "rss_feed")
        self.assertEqual(items[0].trace["feed_format"], "atom")
        self.assertIn("qwen3guard", items[0].summary.lower())

    def test_extract_items_dispatches_rss_feed_strategy(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.google-ai-blog.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_items(fetched)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].title, "Gemini 3.5: frontier intelligence with action")

    def test_fingerprint_ignores_feed_formatting_churn(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.google-ai-blog.fixture.json")[0]
        fetched_original = fetch_source(source, repo_root=ROOT)

        churned_source = source.__class__(
            **{
                **source.__dict__,
                "fixture_path": "tests/fixtures/google_ai_blog_churned.xml",
            }
        )
        fetched_churned = fetch_source(churned_source, repo_root=ROOT)

        original_items = extract_rss_feed(fetched_original)
        churned_items = extract_rss_feed(fetched_churned)

        self.assertEqual(
            [item.fingerprint for item in original_items],
            [item.fingerprint for item in churned_items],
        )

    def test_poll_cli_persists_rss_items_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"

            first = self._run_poll(db_path)
            second = self._run_poll(db_path)

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("新增=3", first.stdout)
            self.assertIn("已存在=0", first.stdout)
            self.assertIn("新增=0", second.stdout)
            self.assertIn("已存在=3", second.stdout)

            with sqlite3.connect(db_path) as connection:
                connection.row_factory = sqlite3.Row
                items = connection.execute(
                    "SELECT source_name, vendor, content_type, title, url, "
                    "detected_at, fingerprint, trace_json, state FROM items ORDER BY id"
                ).fetchall()
                health = connection.execute(
                    "SELECT source_id, ok, item_count FROM source_health ORDER BY id"
                ).fetchall()

            self.assertEqual(len(items), 3)
            self.assertEqual(items[0]["source_name"], "Google AI Blog")
            self.assertEqual(items[0]["vendor"], "Google DeepMind")
            self.assertEqual(items[0]["content_type"], "engineering")
            self.assertTrue(items[0]["detected_at"])
            self.assertTrue(items[0]["fingerprint"])
            self.assertEqual(items[0]["state"], "new")
            trace = json.loads(items[0]["trace_json"])
            self.assertEqual(trace["parser"], "rss_feed")
            self.assertEqual(trace["feed_format"], "rss")
            self.assertEqual([row["ok"] for row in health], [1, 1])
            self.assertEqual([row["item_count"] for row in health], [3, 3])

    def test_poll_cli_persists_atom_items_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"

            first = self._run_poll(db_path, manifest="sources.qwen-blog.fixture.json")
            second = self._run_poll(db_path, manifest="sources.qwen-blog.fixture.json")

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("新增=3", first.stdout)
            self.assertIn("已存在=0", first.stdout)
            self.assertIn("新增=0", second.stdout)
            self.assertIn("已存在=3", second.stdout)

            with sqlite3.connect(db_path) as connection:
                connection.row_factory = sqlite3.Row
                items = connection.execute(
                    "SELECT source_name, vendor, content_type, title, trace_json "
                    "FROM items ORDER BY id"
                ).fetchall()

            self.assertEqual(len(items), 3)
            self.assertEqual(items[0]["source_name"], "Qwen Blog")
            self.assertEqual(items[0]["vendor"], "Qwen")
            trace = json.loads(items[0]["trace_json"])
            self.assertEqual(trace["feed_format"], "atom")

    def _run_poll(
        self,
        db_path: Path,
        manifest: str = "sources.google-ai-blog.fixture.json",
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_info_radar",
                "poll",
                "--manifest",
                str(ROOT / "configs" / manifest),
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


if __name__ == "__main__":
    unittest.main()
