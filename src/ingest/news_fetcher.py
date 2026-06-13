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
from src.ingest.sources import get_rss_feeds
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


async def ingest_rss(task_run_id: str | None = None) -> int:
    import json
    from sqlalchemy import update
    from src.models.schema import TaskRun
    total_saved = 0
    total_fetched = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    enabled_feeds = [f.strip().lower() for f in settings.ENABLED_RSS_FEEDS.split(",") if f.strip()]
    deleted_feeds = [f.strip().lower() for f in settings.DELETED_RSS_FEEDS.split(",") if f.strip()]
    
    # 1. Collect predefined feeds from sources.py
    feeds_to_process = []
    for lang, feeds in get_rss_feeds().items():
        language = LanguageEnum.ZH if lang == "zh" else LanguageEnum.EN
        for f in feeds:
            if f["name"].strip().lower() in deleted_feeds:
                continue
            feeds_to_process.append({
                "info": f,
                "language": language
            })

    # 2. Collect custom feeds from dynamic settings
    if settings.CUSTOM_RSS_FEEDS:
        try:
            custom_list = json.loads(settings.CUSTOM_RSS_FEEDS)
            for f in custom_list:
                lang_enum = LanguageEnum.ZH if f.get("language") == "zh" else LanguageEnum.EN
                feeds_to_process.append({
                    "info": {
                        "name": f["name"],
                        "url": f["url"],
                        "category": f.get("category", "finance"),
                    },
                    "language": lang_enum
                })
        except Exception:
            logger.exception("Failed to parse CUSTOM_RSS_FEEDS setting")

    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        async with async_session_factory() as session:
            for feed_item in feeds_to_process:
                feed_info = feed_item["info"]
                language = feed_item["language"]
                feed_name = feed_info["name"]
                if enabled_feeds and feed_name.strip().lower() not in enabled_feeds:
                    logger.info("Skipping disabled RSS feed: %s", feed_name)
                    continue
                try:
                    count, fetched = await _process_feed(session, client, feed_info, language)
                    total_saved += count
                    total_fetched += fetched
                except Exception:
                    logger.exception("Failed to ingest RSS feed: %s", feed_name)

            if task_run_id:
                try:
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .values(processed_count=total_saved, total_count=total_fetched)
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to update TaskRun metrics for RSS fetch")
    return total_saved


async def _process_feed(
    session: AsyncSession, client: httpx.AsyncClient, feed_info: dict, language: LanguageEnum
) -> tuple[int, int]:
    resp = await client.get(feed_info["url"])
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    saved = 0
    total_entries = len(feed.entries) if feed.entries else 0

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

        article = NewsArticle(
            url=url,
            url_hash=url_hash,
            source_type=SourceTypeEnum.RSS,
            source_name=feed_info["name"],
            language=language,
            title=title,
            content=content[:50000] if content else None,
            content_hash=None,
            summary=None,
            published_at=published_at,
            extra={"category": feed_info.get("category", ""), "feed_name": feed_info["name"]},
            is_relevant=None,
        )
        session.add(article)
        saved += 1

    await session.commit()
    return saved, total_entries