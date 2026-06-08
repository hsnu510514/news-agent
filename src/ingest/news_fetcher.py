from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.llm import check_relevance
from src.ingest.sources import RSS_FEEDS
from src.models.schema import LanguageEnum, NewsArticle, SourceTypeEnum
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _detect_language(url: str, feed_lang: str) -> LanguageEnum:
    if "zh" in feed_lang or any(
        d in url for d in ["36kr", "eastmoney", "sina", "wallstreetcn", "yicai", "caixin"]
    ):
        return LanguageEnum.ZH
    return LanguageEnum.EN


async def ingest_rss() -> int:
    total_saved = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        async with async_session_factory() as session:
            for lang, feeds in RSS_FEEDS.items():
                language = LanguageEnum.ZH if lang == "zh" else LanguageEnum.EN
                for feed_info in feeds:
                    try:
                        count = await _process_feed(session, client, feed_info, language)
                        total_saved += count
                    except Exception:
                        logger.exception("Failed to ingest RSS feed: %s", feed_info["name"])
    return total_saved


async def _process_feed(
    session: AsyncSession, client: httpx.AsyncClient, feed_info: dict, language: LanguageEnum
) -> int:
    resp = await client.get(feed_info["url"])
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    saved = 0

    for entry in feed.entries:
        url = entry.get("link") or entry.get("href", "")
        if not url:
            continue

        url_hash = _hash_url(url)

        existing = await session.execute(
            select(NewsArticle).where(NewsArticle.url_hash == url_hash)
        )
        if existing.scalar_one_or_none():
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        description = entry.get("summary", "") or ""
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        if not content:
            content = description

        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        is_relevant = await check_relevance(title, description)
        if not is_relevant:
            logger.info("Filtered out irrelevant news article: %s", title)
            content = None
            content_hash = None
        else:
            content_hash = _hash_content(content) if content else None

        article = NewsArticle(
            url=url,
            url_hash=url_hash,
            source_type=SourceTypeEnum.RSS,
            source_name=feed_info["name"],
            language=language,
            title=title,
            content=content[:50000] if content else None,
            content_hash=content_hash,
            summary=None,
            published_at=published_at,
            extra={"category": feed_info.get("category", ""), "feed_name": feed_info["name"]},
            is_relevant=is_relevant,
        )
        session.add(article)
        if is_relevant:
            saved += 1

    await session.commit()
    return saved