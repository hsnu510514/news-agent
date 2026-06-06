from __future__ import annotations

import logging

import litellm
from litellm import completion, embedding

from src.core.config import settings

logger = logging.getLogger("news-agent")

litellm.suppress_debug_info = True


async def classify(text: str) -> dict:
    response = await completion(
        model=settings.LLM_CLASSIFY_MODEL,
        messages=[{"role": "user", "content": f"{text}\n\nReturn your response as a valid JSON object only. Do not include any text outside the JSON."}],
        temperature=0.1,
    )
    return response.choices[0].message.content


async def check_relevance(title: str, summary: str) -> bool:
    import json
    prompt = (
        "You are an investment research filter. Analyze the news article title and summary.\n"
        "Determine if it is relevant to:\n"
        "1. Financial News (corporate earnings, stock market, company updates, sector trends, IPOs, mergers).\n"
        "2. Global Affairs & Macro Policy (geopolitics, trade, monetary/fiscal policy, regulations, central banks, elections).\n\n"
        "Return a JSON object with a single boolean field \"relevant\". Do not include any other text.\n\n"
        f"Title: {title}\n"
        f"Summary: {summary or ''}"
    )
    try:
        raw_response = await classify(prompt)
        clean_response = raw_response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.startswith("```"):
            clean_response = clean_response[3:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()
        data = json.loads(clean_response)
        return bool(data.get("relevant", True))
    except Exception as e:
        logger.warning(f"Error checking relevance for title '{title}': {e}")
        return True


async def summarize(text: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})
    response = await completion(
        model=settings.LLM_SUMMARIZE_MODEL,
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content


async def deep_analysis(text: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})
    response = await completion(
        model=settings.LLM_ANALYSIS_MODEL,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content


async def get_embedding(text: str) -> list[float]:
    response = await embedding(
        model=settings.LLM_EMBED_MODEL,
        input=[text],
    )
    return response.data[0]["embedding"]