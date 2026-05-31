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

from ai_info_radar.extractors import extract_claude_code_changelog  # noqa: E402
from ai_info_radar.fetchers import fetch_source  # noqa: E402
from ai_info_radar.manifest import load_sources  # noqa: E402


class ClaudeCodeChangelogIssueTests(unittest.TestCase):
    def test_manifest_loads_official_claude_code_changelog_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.claude-code.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "claude-code-changelog")
        self.assertEqual(source.vendor, "Anthropic")
        self.assertEqual(source.authority_level, "official")
        self.assertEqual(source.parsing_strategy, "claude_code_changelog")
        self.assertEqual(source.content_type, "developer_changelog")

    def test_extraction_normalizes_version_sections(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.claude-code.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_claude_code_changelog(fetched)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Claude Code 1.2.3")
        self.assertEqual(
            items[0].url,
            "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md#1-2-3",
        )
        self.assertIsNone(items[0].published_at)
        self.assertEqual(items[0].vendor, "Anthropic")
        self.assertEqual(items[0].content_type, "developer_changelog")
        self.assertEqual(items[0].authority_level, "official")
        self.assertEqual(items[0].trace["parser"], "claude_code_changelog")
        self.assertEqual(items[0].trace["entry_id"], "1-2-3")
        self.assertIn("MCP server permission controls", items[0].summary)
        self.assertIn("agent workflows", items[0].summary)

    def test_summary_preserves_classification_terms_for_downstream_rules(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.claude-code.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_claude_code_changelog(fetched)
        second_summary = items[1].summary.lower()

        for term in ["breaking change", "migrated", "deprecated", "agent workflow"]:
            self.assertIn(term, second_summary)

    def test_fingerprint_ignores_docs_shell_chrome_and_recommendation_churn(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.claude-code.fixture.json")[0]
        fetched_original = fetch_source(source, repo_root=ROOT)

        churned_source = source.__class__(
            **{
                **source.__dict__,
                "fixture_path": "tests/fixtures/claude_code_changelog_churned.md",
            }
        )
        fetched_churned = fetch_source(churned_source, repo_root=ROOT)

        original_items = extract_claude_code_changelog(fetched_original)
        churned_items = extract_claude_code_changelog(fetched_churned)

        self.assertEqual(
            [item.fingerprint for item in original_items],
            [item.fingerprint for item in churned_items],
        )

    def test_poll_cli_persists_changelog_items_and_is_idempotent(self) -> None:
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
                    "summary, trace_json, state FROM items ORDER BY id"
                ).fetchall()

            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["source_name"], "Claude Code Changelog")
            self.assertEqual(items[0]["vendor"], "Anthropic")
            self.assertEqual(items[0]["content_type"], "developer_changelog")
            self.assertEqual(items[0]["state"], "new")
            self.assertTrue(items[0]["url"].endswith("#1-2-3"))
            self.assertIn("MCP", items[0]["summary"])
            self.assertIn("Breaking change", items[1]["summary"])
            self.assertEqual(json.loads(items[0]["trace_json"])["entry_id"], "1-2-3")

    def _run_poll(self, db_path: Path) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        return subprocess.run(
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


if __name__ == "__main__":
    unittest.main()
