from __future__ import annotations

import json
from typing import Callable, Protocol
from urllib import request
from urllib.error import URLError

from .models import AlertDeliveryResult, AlertMessage


class UrlOpenLike(Protocol):
    def __call__(self, req: request.Request, timeout: float) -> object:
        ...


def build_feishu_payload(message: AlertMessage) -> dict[str, object]:
    lines = [
        f"[{message.short_id}] {message.title}",
        f"来源：{message.source}",
        f"权威级别：{message.authority}",
        f"触发原因：{message.why_it_matters}",
        f"原始链接：{message.original_link}",
    ]
    if message.supporting_sources:
        lines.append(f"支持来源：{', '.join(message.supporting_sources)}")
    if message.matched_terms:
        lines.append(f"命中关键词：{', '.join(message.matched_terms)}")

    return build_feishu_text_payload("\n".join(lines))


def build_feishu_text_payload(text: str) -> dict[str, object]:
    return {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }


def send_feishu_webhook(
    webhook_url: str,
    message: AlertMessage,
    *,
    timeout_seconds: float = 10.0,
    opener: UrlOpenLike | None = None,
) -> AlertDeliveryResult:
    payload = build_feishu_payload(message)
    return send_feishu_payload(
        webhook_url,
        payload,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )


def send_feishu_text_webhook(
    webhook_url: str,
    text: str,
    *,
    timeout_seconds: float = 10.0,
    opener: UrlOpenLike | None = None,
) -> AlertDeliveryResult:
    payload = build_feishu_text_payload(text)
    return send_feishu_payload(
        webhook_url,
        payload,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )


def send_feishu_payload(
    webhook_url: str,
    payload: dict[str, object],
    *,
    timeout_seconds: float = 10.0,
    opener: UrlOpenLike | None = None,
) -> AlertDeliveryResult:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    transport: Callable[[request.Request, float], object] = opener or request.urlopen
    try:
        response = transport(req, timeout_seconds)
    except URLError as exc:
        return AlertDeliveryResult(ok=False, message=str(exc), payload=payload)

    status_code = getattr(response, "status", getattr(response, "code", None))
    body = _read_response_body(response)
    ok = status_code is not None and 200 <= int(status_code) < 300
    return AlertDeliveryResult(
        ok=ok,
        status_code=int(status_code) if status_code is not None else None,
        message=body,
        payload=payload,
    )


def _read_response_body(response: object) -> str:
    read = getattr(response, "read", None)
    if not callable(read):
        return ""
    raw = read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)
