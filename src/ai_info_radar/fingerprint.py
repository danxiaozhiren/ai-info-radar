from __future__ import annotations

from hashlib import sha256


def content_fingerprint(
    *,
    title: str,
    url: str,
    published_at: str | None,
    summary: str,
    vendor: str,
    content_type: str,
) -> str:
    parts = [
        normalize_text(vendor),
        normalize_text(content_type),
        normalize_text(title),
        normalize_url(url),
        normalize_text(published_at or ""),
        normalize_text(summary),
    ]
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def normalize_url(value: str) -> str:
    return value.strip().split("#", 1)[0].rstrip("/").lower()
