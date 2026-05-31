from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

from .models import FetchedSource, Source, utc_now_iso


class FetchError(RuntimeError):
    pass


def fetch_source(source: Source, repo_root: str | Path, timeout_seconds: float = 10.0) -> FetchedSource:
    fetched_at = utc_now_iso()
    if source.fixture_path:
        path = Path(repo_root) / source.fixture_path
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise FetchError(f"无法读取 {source.id} 的本地夹具：{path}") from exc
        return FetchedSource(source=source, body=body, fetched_at=fetched_at, final_url=source.url)

    request = Request(source.url, headers={"User-Agent": "ai-info-radar/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
            final_url = response.geturl()
    except OSError as exc:
        raise FetchError(f"无法抓取 {source.id}：{exc}") from exc

    return FetchedSource(source=source, body=body, fetched_at=fetched_at, final_url=final_url)
