from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ai_info_radar.digest import build_digest_content, render_digest_markdown  # noqa: E402
from ai_info_radar.store import RadarStore  # noqa: E402


def main() -> None:
    db = Path.home() / "Library" / "Application Support" / "ai-info-radar" / "radar.sqlite"
    report_date = date(2026, 5, 31)
    with RadarStore(db) as store:
        content = build_digest_content(store, report_date)
        md = render_digest_markdown(content)
        report_path = Path.home() / "Documents" / "ai-info-radar-reports" / f"ai-radar-digest-{report_date.isoformat()}.md"
        report_path.write_text(md, encoding="utf-8")
        print(md)


if __name__ == "__main__":
    main()
