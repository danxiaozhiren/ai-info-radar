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

from ai_info_radar.classifier import classify_item  # noqa: E402
from ai_info_radar.extractors import extract_official_model_pricing  # noqa: E402
from ai_info_radar.fetchers import fetch_source  # noqa: E402
from ai_info_radar.manifest import load_sources  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


class PricingModelDeprecationIssueTests(unittest.TestCase):
    def test_manifest_loads_official_pricing_source(self) -> None:
        sources = load_sources(ROOT / "configs" / "sources.openai-pricing.fixture.json")

        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source.id, "openai-api-pricing")
        self.assertEqual(source.vendor, "OpenAI")
        self.assertEqual(source.authority_level, "official")
        self.assertEqual(source.url, "https://platform.openai.com/docs/pricing/")
        self.assertEqual(source.parsing_strategy, "official_model_pricing")
        self.assertEqual(source.content_type, "pricing")

    def test_extractor_normalizes_meaningful_model_pricing_fields(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.openai-pricing.fixture.json")[0]
        fetched = fetch_source(source, repo_root=ROOT)

        items = extract_official_model_pricing(fetched)

        self.assertEqual(len(items), 2)
        current = items[0]
        legacy = items[1]
        self.assertEqual(current.title, "Model pricing: gpt-5-mini")
        self.assertEqual(current.url, "https://platform.openai.com/docs/pricing/#gpt-5-mini")
        self.assertIn("Input price: $0.25", current.summary)
        self.assertIn("Output price: $2.00", current.summary)

        self.assertEqual(legacy.title, "Model pricing: gpt-4o")
        self.assertIn("Input price: $2.50", legacy.summary)
        self.assertIn("Output price: $10.00", legacy.summary)

    def test_fingerprint_ignores_layout_chrome_and_recommendation_churn(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.openai-pricing.fixture.json")[0]
        fetched_original = fetch_source(source, repo_root=ROOT)
        churned_source = source.__class__(
            **{
                **source.__dict__,
                "fixture_path": "tests/fixtures/openai_pricing_models_churned.html",
            }
        )
        fetched_churned = fetch_source(churned_source, repo_root=ROOT)

        original_items = extract_official_model_pricing(fetched_original)
        churned_items = extract_official_model_pricing(fetched_churned)

        self.assertEqual(
            [item.fingerprint for item in original_items],
            [item.fingerprint for item in churned_items],
        )

    def test_fingerprint_changes_for_substantive_model_pricing_and_deprecation_changes(self) -> None:
        source = load_sources(ROOT / "configs" / "sources.openai-pricing.fixture.json")[0]
        fetched_original = fetch_source(source, repo_root=ROOT)
        changed_source = source.__class__(
            **{
                **source.__dict__,
                "fixture_path": "tests/fixtures/openai_pricing_models_changed.html",
            }
        )
        fetched_changed = fetch_source(changed_source, repo_root=ROOT)

        original_items = extract_official_model_pricing(fetched_original)
        changed_items = extract_official_model_pricing(fetched_changed)

        self.assertNotEqual(
            [item.fingerprint for item in original_items],
            [item.fingerprint for item in changed_items],
        )
        self.assertIn("Input price: $0.20", changed_items[0].summary)
        self.assertIn("Output price: $1.60", changed_items[0].summary)
        self.assertIn("Input price: $3.00", changed_items[1].summary)

    def test_substantive_official_pricing_items_classify_as_strong_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"
            self._run_poll(db_path)

            with RadarStore(db_path) as store:
                items = {item.title: item for item in store.list_items()}

            current_decision = classify_item(items["Model pricing: gpt-5-mini"])
            legacy_decision = classify_item(items["Model pricing: gpt-4o"])

            self.assertTrue(current_decision.should_alert)
            self.assertEqual(current_decision.severity, "critical")
            self.assertIn("pricing", current_decision.matched_terms)
            self.assertIn("input price", current_decision.matched_terms)

            self.assertTrue(legacy_decision.should_alert)
            self.assertIn("pricing", legacy_decision.matched_terms)

    def test_poll_cli_persists_pricing_items_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "radar.sqlite"

            first = self._run_poll(db_path)
            second = self._run_poll(db_path)

            self.assertIn("新增=2", first.stdout)
            self.assertIn("已存在=0", first.stdout)
            self.assertIn("新增=0", second.stdout)
            self.assertIn("已存在=2", second.stdout)

    def _run_poll(self, db_path: Path) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_info_radar",
                "poll",
                "--manifest",
                str(ROOT / "configs" / "sources.openai-pricing.fixture.json"),
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
