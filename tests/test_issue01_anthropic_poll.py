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

from ai_info_radar.extractors import extract_anthropic_engineering  # noqa: E402
from ai_info_radar.fetchers import fetch_source  # noqa: E402
from ai_info_radar.manifest import ManifestError, load_sources  # noqa: E402


class AnthropicPollIssueTests(unittest.TestCase):
    def test_manifest_loads_curated_anthropic_engineering_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.anthropic.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "anthropic-engineering")
        self.assertEqual(source.vendor, "Anthropic")
        self.assertEqual(source.authority_level, "official")
        self.assertEqual(source.parsing_strategy, "anthropic_engineering_index")
        self.assertEqual(source.content_type, "engineering")

    def test_manifest_rejects_malformed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "bad.json"
            manifest.write_text(json.dumps({"sources": [{"id": "bad"}]}), encoding="utf-8")

            with self.assertRaises(ManifestError):
                load_sources(manifest)

    def test_extraction_normalizes_anthropic_engineering_items(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.anthropic.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_anthropic_engineering(fetched)

        self.assertEqual(len(items), 2)
        self.assertEqual(
            items[0].title,
            "Scaling Managed Agents: Decoupling the brain from the hands",
        )
        self.assertEqual(items[0].url, "https://www.anthropic.com/engineering/managed-agents")
        self.assertEqual(items[0].published_at, "2026-04-08")
        self.assertEqual(items[0].vendor, "Anthropic")
        self.assertEqual(items[0].content_type, "engineering")
        self.assertEqual(items[0].authority_level, "official")
        self.assertEqual(items[0].trace["parser"], "anthropic_engineering_index")

    def test_fingerprint_ignores_page_chrome_and_recommendation_churn(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.anthropic.fixture.json")[0]
        fetched_original = fetch_source(source, repo_root=ROOT)

        churned_source = source.__class__(
            **{
                **source.__dict__,
                "fixture_path": "tests/fixtures/anthropic_engineering_churned.html",
            }
        )
        fetched_churned = fetch_source(churned_source, repo_root=ROOT)

        original_items = extract_anthropic_engineering(fetched_original)
        churned_items = extract_anthropic_engineering(fetched_churned)

        self.assertEqual(
            [item.fingerprint for item in original_items],
            [item.fingerprint for item in churned_items],
        )

    def test_poll_cli_persists_items_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"

            first = self._run_poll(db_path)
            second = self._run_poll(db_path)

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("新增=2", first.stdout)
            self.assertIn("已存在=0", first.stdout)
            self.assertIn("新增=0", second.stdout)
            self.assertIn("已存在=2", second.stdout)

            with sqlite3.connect(db_path) as connection:
                connection.row_factory = sqlite3.Row
                items = connection.execute(
                    "SELECT source_name, vendor, content_type, title, url, published_at, "
                    "detected_at, fingerprint, trace_json, state FROM items ORDER BY id"
                ).fetchall()
                health = connection.execute(
                    "SELECT source_id, ok, item_count FROM source_health ORDER BY id"
                ).fetchall()

            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["source_name"], "Anthropic Engineering")
            self.assertEqual(items[0]["vendor"], "Anthropic")
            self.assertEqual(items[0]["content_type"], "engineering")
            self.assertTrue(items[0]["detected_at"])
            self.assertTrue(items[0]["fingerprint"])
            self.assertEqual(items[0]["state"], "new")
            self.assertIn("fetched_url", json.loads(items[0]["trace_json"]))
            self.assertEqual([row["ok"] for row in health], [1, 1])
            self.assertEqual([row["item_count"] for row in health], [2, 2])

    def test_poll_records_source_failure_without_stopping_successful_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            manifest_path = Path(temp_dir) / "sources.json"
            source = json.loads((ROOT / "configs" / "sources.anthropic.fixture.json").read_text())
            bad_source = {
                **source["sources"][0],
                "id": "broken-anthropic-engineering",
                "fixture_path": "tests/fixtures/missing.html",
            }
            source["sources"].append(bad_source)
            manifest_path.write_text(json.dumps(source), encoding="utf-8")

            result = self._run_poll(db_path, manifest_path=manifest_path)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("新增=2", result.stdout)
            self.assertIn("失败=1", result.stdout)

            with sqlite3.connect(db_path) as connection:
                item_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
                failures = connection.execute(
                    "SELECT source_id, ok, message FROM source_health WHERE ok = 0"
                ).fetchall()

            self.assertEqual(item_count, 2)
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0][0], "broken-anthropic-engineering")
            self.assertIn("无法读取", failures[0][2])

    def _run_poll(
        self,
        db_path: Path,
        manifest_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_info_radar",
                "poll",
                "--manifest",
                str(manifest_path or ROOT / "configs" / "sources.anthropic.fixture.json"),
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
