from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.llm import check_relevance
from src.models.schema import NewsArticle, SourceTypeEnum, LanguageEnum
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")

NEWSAPI_BASE = "https://newsapi.org/v2"


async def ingest_newsapi(task_run_id: str | None = None) -> int:
    if not settings.NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set, skipping NewsAPI ingestion")
        return 0

    from sqlalchemy import update
    from src.models.schema import TaskRun
    total_saved = 0
    total_fetched = 0
    queries = [
        ("en", "stock market OR earnings OR federal reserve OR economy OR cryptocurrency OR bitcoin OR ethereum"),
        ("zh", "A股 OR 经济 OR 央行 OR 财报"),
    ]

    async with async_session_factory() as session:
        for lang, query in queries:
            try:
                count, fetched = await _fetch_newsapi(session, lang, query)
                total_saved += count
                total_fetched += fetched
            except Exception:
                logger.exception("Failed to ingest NewsAPI for lang=%s", lang)

        if task_run_id:
            try:
                await session.execute(
                    update(TaskRun)
                    .where(TaskRun.id == task_run_id)
                    .values(processed_count=total_saved, total_count=total_fetched)
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to update TaskRun metrics for NewsAPI fetch")

    return total_saved


async def _fetch_newsapi(session: AsyncSession, lang: str, query: str) -> tuple[int, int]:
    import hashlib

    url = f"{NEWSAPI_BASE}/everything"
    params = {
        "q": query,
        "language": lang,
        "sortBy": "publishedAt",
        "pageSize": 100,
        "apiKey": settings.NEWSAPI_KEY,
    }
    if settings.NEWSAPI_DOMAINS:
        params["domains"] = settings.NEWSAPI_DOMAINS

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30.0)
        data = resp.json()

    if data.get("status") != "ok":
        logger.error("NewsAPI error: %s", data.get("message", "unknown"))
        return 0, 0

    saved = 0
    articles = data.get("articles", [])

    for art in articles:
        article_url = art.get("url", "")
        if not article_url:
            continue

        url_hash = hashlib.sha256(article_url.encode()).hexdigest()

        existing = await session.execute(
            select(NewsArticle).where(NewsArticle.url_hash == url_hash)
        )
        if existing.scalar_one_or_none():
            continue

        title = art.get("title", "").strip()
        if not title or title == "[Removed]":
            continue

        description = art.get("description") or ""
        content = art.get("content") or description

        published_at = None
        published_str = art.get("publishedAt")
        if published_str:
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except Exception:
                pass

        language = LanguageEnum.ZH if lang == "zh" else LanguageEnum.EN

        article = NewsArticle(
            url=article_url,
            url_hash=url_hash,
            source_type=SourceTypeEnum.NEWSAPI,
            source_name=art.get("source", {}).get("name", "NewsAPI"),
            language=language,
            title=title,
            content=content[:50000] if content else None,
            content_hash=None,
            summary=description,
            published_at=published_at,
            extra={
                "author": art.get("author", ""),
                "image_url": art.get("urlToImage", ""),
            },
            is_relevant=None,
        )
        session.add(article)
        saved += 1

    await session.commit()
    return saved, len(articles)