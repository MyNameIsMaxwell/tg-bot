"""DeepSeek API integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


@dataclass
class SummaryResult:
    text: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


def _format_messages(messages: List[Dict[str, Any]]) -> str:
    lines = []
    for msg in messages:
        text = msg.get("text", "").strip()
        link = msg.get("link")
        if not text:
            continue
        if link:
            lines.append(f"{text}\nСсылка: {link}")
        else:
            lines.append(text)
    if not lines:
        return "Нет новых сообщений."
    joined = "\n\n".join(lines)
    return (
        "Составь краткую, приоритезированную сводку (3–7 пунктов). "
        "Пиши по делу, без упоминания источников/каналов. "
        "Если у пункта есть ссылка, обязательно включи этот URL в текст пункта (сырая ссылка, один раз на пункт). "
        "Не добавляй служебные блоки вроде [INFO]. "
        "Используй эмодзи по желанию, но умеренно.\n\n"
        f"{joined}"
    )


async def summarize_messages(messages: List[Dict[str, Any]]) -> SummaryResult:
    """Send messages to DeepSeek and return the summary text + usage."""
    prompt = _format_messages(messages)
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You summarize Telegram news digests in Russian."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("DeepSeek error %s: %s", exc.response.status_code, exc.response.text)
            raise

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("DeepSeek returned no choices")

        usage = data.get("usage") or {}
        result = SummaryResult(
            text=choices[0]["message"]["content"].strip(),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
        return result



