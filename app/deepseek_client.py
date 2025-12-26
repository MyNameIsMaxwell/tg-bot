"""DeepSeek API integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from .config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

# Structured system prompt with clear role and rules
SYSTEM_PROMPT = """Ты — AI-редактор новостных дайджестов. Твоя задача — создавать краткие, информативные сводки из Telegram-постов.

## Твоя роль:
Ты профессиональный редактор, который выделяет главное из потока новостей и представляет информацию в удобном для быстрого чтения формате.

## Правила составления сводки:
1. Пиши ТОЛЬКО на русском языке
2. Создавай от 3 до 7 пунктов — не больше, не меньше
3. Каждый пункт — максимум 1-2 коротких предложения
4. Приоритизируй по важности: самое важное/срочное — в начале
5. Группируй схожие темы, если это уместно
6. Ссылку размещай в конце пункта, без markdown-форматирования
7. Используй эмодзи умеренно — только для визуального разделения тем (📌 для главного, • для остальных)

## Формат вывода:
📌 Главная новость в одном предложении https://t.me/...
• Вторая по важности новость https://t.me/...
• Третья новость https://t.me/...

## Строгие ограничения — НЕ делай:
- НЕ упоминай названия каналов или источников
- НЕ добавляй вводные фразы ("Вот ваша сводка...", "Сегодня произошло...")
- НЕ используй markdown (жирный, курсив, заголовки)
- НЕ добавляй метки [INFO], [SOURCE], [ВАЖНО] и подобные
- НЕ дублируй информацию между пунктами
- НЕ добавляй заключительные фразы ("Это все новости...")
- НЕ нумеруй пункты цифрами

## Пример хорошей сводки:
📌 ЦБ повысил ключевую ставку до 16% годовых https://t.me/channel/123
• Курс доллара превысил 90 рублей на фоне решения регулятора https://t.me/channel/456
• Минфин анонсировал новые меры поддержки ипотечных заёмщиков https://t.me/channel/789"""

# User prompt template
USER_PROMPT_TEMPLATE = """Проанализируй следующие посты и составь краткую сводку по правилам выше.

---
ПОСТЫ ДЛЯ АНАЛИЗА:
{posts}
---

Составь сводку:"""


@dataclass
class SummaryResult:
    text: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


def _format_posts_for_prompt(messages: List[Dict[str, Any]]) -> str:
    """Format messages into a structured list for the prompt."""
    formatted_posts = []
    for i, msg in enumerate(messages, 1):
        text = msg.get("text", "").strip()
        link = msg.get("link", "")
        if not text:
            continue
        post_block = f"[Пост {i}]\n{text}"
        if link:
            post_block += f"\nСсылка: {link}"
        formatted_posts.append(post_block)
    
    if not formatted_posts:
        return ""
    
    return "\n\n".join(formatted_posts)


def _build_user_prompt(messages: List[Dict[str, Any]]) -> str:
    """Build the user prompt with formatted posts."""
    posts_text = _format_posts_for_prompt(messages)
    if not posts_text:
        return "Нет новых сообщений для анализа."
    return USER_PROMPT_TEMPLATE.format(posts=posts_text)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_deepseek_api(payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """Make the actual API call to DeepSeek with retry logic.
    
    This is separated from summarize_messages to allow retry only on the API call,
    not on the message formatting.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("DeepSeek error %s: %s", exc.response.status_code, exc.response.text)
            # Don't retry on 4xx client errors (except 429 rate limit)
            if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            raise
        return response.json()


async def summarize_messages(
    messages: List[Dict[str, Any]],
    custom_instructions: Optional[str] = None,
) -> SummaryResult:
    """Send messages to DeepSeek and return the summary text + usage.
    
    Args:
        messages: List of message dicts with 'text' and optional 'link' keys.
        custom_instructions: Optional custom prompt that REPLACES the default system prompt.
                             If empty or None, the default SYSTEM_PROMPT is used.
    
    Returns:
        SummaryResult with the generated summary and token usage stats.
    
    Raises:
        httpx.HTTPStatusError: If the API request fails after retries.
        RuntimeError: If DeepSeek returns no choices.
    """
    if not messages:
        return SummaryResult(text="Нет новых сообщений.", prompt_tokens=0, completion_tokens=0, total_tokens=0)
    
    user_prompt = _build_user_prompt(messages)
    
    # Use custom prompt if provided, otherwise fall back to default system prompt
    if custom_instructions and custom_instructions.strip():
        system_content = custom_instructions.strip()
        logger.info("Using custom prompt for summarization")
    else:
        system_content = SYSTEM_PROMPT
    
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    
    # Adjust max_tokens based on number of messages
    max_tokens = min(800, 100 + len(messages) * 50)
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,  # Slightly higher for more natural language
        "max_tokens": max_tokens,
        "top_p": 0.9,
    }

    try:
        data = await _call_deepseek_api(payload, headers)
    except Exception as exc:
        logger.error("DeepSeek API call failed after retries: %s", exc)
        raise

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
    logger.info(
        "DeepSeek summary generated: %d messages -> %d tokens",
        len(messages),
        result.total_tokens or 0,
    )
    return result



