from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.manifest import ManifestError, load_sources  # noqa: E402


MANIFEST = ROOT / "configs" / "sources.official.json"
REQUIRED_FIELDS = {
    "id",
    "name",
    "vendor",
    "source_type",
    "authority_level",
    "url",
    "priority",
    "parsing_strategy",
    "content_type",
    "enabled",
}


class OfficialSourceManifestIssueTests(unittest.TestCase):
    def test_official_manifest_is_governance_map_and_default_disabled(self) -> None:
        enabled_sources = load_sources(MANIFEST)
        all_sources = load_sources(MANIFEST, include_disabled=True)

        self.assertEqual(enabled_sources, [])
        self.assertGreaterEqual(len(all_sources), 35)
        self.assertTrue(all(not source.enabled for source in all_sources))

    def test_anthropic_and_openai_required_coverage_present(self) -> None:
        source_ids = {source.id for source in load_sources(MANIFEST, include_disabled=True)}

        anthropic_required = {
            "anthropic-news",
            "anthropic-engineering",
            "anthropic-research",
            "anthropic-api-release-notes",
            "anthropic-claude-code-changelog",
            "anthropic-claude-apps-release-notes",
            "anthropic-claude-code-github-changelog",
            "anthropic-status-incidents",
        }
        openai_required = {
            "openai-news",
            "openai-status-incidents",
            "openai-docs-changelog",
            "openai-api-pricing",
            "openai-models",
            "openai-deprecations",
            "openai-python-releases",
            "openai-node-releases",
        }

        self.assertTrue(anthropic_required <= source_ids, sorted(anthropic_required - source_ids))
        self.assertTrue(openai_required <= source_ids, sorted(openai_required - source_ids))

    def test_vendor_placeholders_present_for_initial_non_anthropic_openai_coverage(self) -> None:
        sources = load_sources(MANIFEST, include_disabled=True)

        for vendor in ("Qwen", "DeepSeek", "Mistral", "Google DeepMind"):
            vendor_sources = [source for source in sources if source.vendor == vendor]
            self.assertTrue(vendor_sources, vendor)
            self.assertTrue(
                any(source.parsing_strategy == "placeholder" for source in vendor_sources),
                vendor,
            )

    def test_agent_workflow_source_map_present(self) -> None:
        sources = load_sources(MANIFEST, include_disabled=True)
        search_text = "\n".join(
            f"{source.id} {source.name} {source.vendor} {source.content_type}" for source in sources
        ).lower()

        for term in ("codex", "claude code", "cursor", "opencode", "mcp", "agents sdk", "github copilot"):
            self.assertIn(term, search_text)

    def test_every_entry_has_required_governance_fields(self) -> None:
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = raw["sources"]
        loaded_ids = {source.id for source in load_sources(MANIFEST, include_disabled=True)}
        raw_ids: list[str] = []

        for index, entry in enumerate(entries):
            source_id = entry.get("id", f"index {index}")
            self.assertTrue(REQUIRED_FIELDS <= entry.keys(), source_id)
            self.assertIsInstance(entry["enabled"], bool, source_id)
            self.assertIsInstance(entry["priority"], int, source_id)
            self.assertTrue(entry["url"].startswith("https://"), source_id)
            raw_ids.append(entry["id"])

        self.assertEqual(len(raw_ids), len(set(raw_ids)))
        self.assertEqual(set(raw_ids), loaded_ids)

    def test_manifest_validation_rejects_incomplete_unapproved_and_duplicate_entries(self) -> None:
        good_entry = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"][0]

        with self.subTest("missing enabled"):
            incomplete = dict(good_entry)
            incomplete.pop("enabled")
            with self.assertRaises(ManifestError):
                self._load_temp_manifest([incomplete])

        for field, value in (
            ("authority_level", "vendor_blog"),
            ("source_type", "newsletter"),
            ("parsing_strategy", "markdown_magic"),
        ):
            with self.subTest(field=field):
                unapproved = {**good_entry, field: value}
                with self.assertRaises(ManifestError):
                    self._load_temp_manifest([unapproved])

        with self.subTest("non boolean enabled"):
            non_boolean = {**good_entry, "enabled": "false"}
            with self.assertRaises(ManifestError):
                self._load_temp_manifest([non_boolean])

        with self.subTest("duplicate ids"):
            duplicate = {**good_entry, "name": "Duplicate Anthropic News"}
            with self.assertRaises(ManifestError):
                self._load_temp_manifest([good_entry, duplicate])

    def _load_temp_manifest(self, sources: list[dict[str, Any]]) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "sources.json"
            manifest.write_text(json.dumps({"sources": sources}), encoding="utf-8")
            load_sources(manifest, include_disabled=True)


if __name__ == "__main__":
    unittest.main()
