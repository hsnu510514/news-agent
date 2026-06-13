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


from typing import Sequence
from src.ingest.interface import BaseIngestAdapter, IngestionSourceType

class NewsApiIngestAdapter(BaseIngestAdapter):
    async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[NewsArticle]:
        if not settings.NEWSAPI_KEY:
            logger.warning("NEWSAPI_KEY not set, skipping NewsAPI ingestion")
            return []

        import hashlib
        queries = [
            ("en", "stock market OR earnings OR federal reserve OR economy OR cryptocurrency OR bitcoin OR ethereum"),
            ("zh", "A股 OR 经济 OR 央行 OR 财报"),
        ]
        
        articles = []
        for lang, query in queries:
            try:
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

                resp = await client.get(url, params=params, timeout=30.0)
                data = resp.json()

                if data.get("status") != "ok":
                    logger.error("NewsAPI error for lang=%s: %s", lang, data.get("message", "unknown"))
                    continue

                lang_articles = data.get("articles", [])
                for art in lang_articles:
                    article_url = art.get("url", "")
                    if not article_url:
                        continue

                    url_hash = hashlib.sha256(article_url.encode()).hexdigest()
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
                    articles.append(article)
            except Exception:
                logger.exception("Failed to fetch/parse NewsAPI for lang=%s", lang)

        return articles

    async def filter_duplicates(self, items: Sequence[NewsArticle], session: AsyncSession) -> Sequence[NewsArticle]:
        if not items:
            return []

        # Deduplicate the list itself by url_hash first
        unique_fetched = {}
        for item in items:
            unique_fetched[item.url_hash] = item

        url_hashes = list(unique_fetched.keys())
        stmt = select(NewsArticle.url_hash).where(NewsArticle.url_hash.in_(url_hashes))
        res = await session.execute(stmt)
        existing_hashes = {row[0] for row in res.all()}

        return [item for item in unique_fetched.values() if item.url_hash not in existing_hashes]


# Register the adapter
from src.ingest.pipeline import register_adapter
register_adapter(IngestionSourceType.NEWSAPI, NewsApiIngestAdapter())


# Deprecated shim wrapper
async def ingest_newsapi(task_run_id: str | None = None) -> int:
    """Deprecated: use src.ingest.pipeline.ingest_source instead."""
    from src.ingest.pipeline import ingest_source
    summary = await ingest_source(IngestionSourceType.NEWSAPI, task_run_id)
    return summary.saved_count