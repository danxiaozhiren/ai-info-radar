from __future__ import annotations

import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "operations" / "launchd-deployment.md"
POLL_PLIST = ROOT / "docs" / "launchd" / "com.abi.ai-info-radar.poll.plist.example"
DIGEST_PLIST = ROOT / "docs" / "launchd" / "com.abi.ai-info-radar.digest.plist.example"


class LaunchdDeploymentDocsIssueTests(unittest.TestCase):
    def test_deployment_doc_covers_install_config_launchd_smoke_and_secrets(self) -> None:
        text = DOC.read_text(encoding="utf-8")

        for expected in (
            "PYTHONPATH=src /opt/homebrew/bin/python3 -m ai_info_radar --help",
            "sources.local.json",
            "rules.local.json",
            "FEISHU_WEBHOOK_URL",
            "chmod 600",
            "StartInterval",
            "StartCalendarInterval",
            "launchctl bootstrap",
            "launchctl kickstart",
            "失败=1",
            "daily",
            "Do not commit",
        ):
            self.assertIn(expected, text)

    def test_poll_launchd_template_runs_every_ten_minutes(self) -> None:
        plist = plistlib.loads(POLL_PLIST.read_bytes())
        command = plist["ProgramArguments"][-1]

        self.assertEqual(plist["Label"], "com.abi.ai-info-radar.poll")
        self.assertEqual(plist["StartInterval"], 600)
        self.assertIn("AI_INFO_RADAR_ENV", plist["EnvironmentVariables"])
        self.assertIn("-m ai_info_radar poll", command)
        self.assertIn("--manifest \"$AI_INFO_RADAR_MANIFEST\"", command)
        self.assertTrue(plist["StandardOutPath"].endswith("poll.out.log"))
        self.assertTrue(plist["StandardErrorPath"].endswith("poll.err.log"))

    def test_digest_launchd_template_runs_each_morning(self) -> None:
        plist = plistlib.loads(DIGEST_PLIST.read_bytes())
        command = plist["ProgramArguments"][-1]

        self.assertEqual(plist["Label"], "com.abi.ai-info-radar.digest")
        self.assertEqual(plist["StartCalendarInterval"], {"Hour": 8, "Minute": 0})
        self.assertIn("AI_INFO_RADAR_ENV", plist["EnvironmentVariables"])
        self.assertIn("-m ai_info_radar daily", command)
        self.assertIn("--reports-dir \"$AI_INFO_RADAR_REPORT_DIR\"", command)
        self.assertTrue(plist["StandardOutPath"].endswith("digest.out.log"))
        self.assertTrue(plist["StandardErrorPath"].endswith("digest.err.log"))

    def test_gitignore_blocks_runtime_data_and_secrets(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        for expected in (
            "var/",
            "data/",
            "logs/",
            "reports/",
            "*.sqlite",
            ".env",
            ".env.*",
            "secrets/",
            "*.local.json",
            "*.local.plist",
            "*.secret",
            "*.key",
        ):
            self.assertIn(expected, gitignore)


if __name__ == "__main__":
    unittest.main()
