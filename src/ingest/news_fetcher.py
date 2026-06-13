from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Sequence

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.ingest.interface import BaseIngestAdapter, IngestionSourceType
from src.ingest.sources import get_rss_feeds
from src.models.schema import LanguageEnum, NewsArticle, SourceTypeEnum

logger = logging.getLogger("news-agent")


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


class RssIngestAdapter(BaseIngestAdapter):
    """Adapter for RSS feed ingestion."""

    async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[NewsArticle]:
        import json
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

        articles = []
        for feed_item in feeds_to_process:
            feed_info = feed_item["info"]
            language = feed_item["language"]
            feed_name = feed_info["name"]
            if enabled_feeds and feed_name.strip().lower() not in enabled_feeds:
                logger.info("Skipping disabled RSS feed: %s", feed_name)
                continue
            try:
                resp = await client.get(feed_info["url"])
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)

                for entry in feed.entries:
                    url = entry.get("link") or entry.get("href", "")
                    if not url:
                        continue

                    url_hash = _hash_url(url)
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
                    articles.append(article)
            except Exception:
                logger.exception("Failed to ingest RSS feed: %s", feed_name)

        return articles

    async def filter_duplicates(self, items: Sequence[NewsArticle], session: AsyncSession) -> Sequence[NewsArticle]:
        if not items:
            return []
        
        # Deduplicate the list itself by url_hash first
        unique_fetched = {}
        for item in items:
            unique_fetched[item.url_hash] = item
        
        # Bulk query existing hashes
        url_hashes = list(unique_fetched.keys())
        stmt = select(NewsArticle.url_hash).where(NewsArticle.url_hash.in_(url_hashes))
        res = await session.execute(stmt)
        existing_hashes = {row[0] for row in res.all()}
        
        return [item for item in unique_fetched.values() if item.url_hash not in existing_hashes]


# Register the adapter
from src.ingest.pipeline import register_adapter
register_adapter(IngestionSourceType.RSS, RssIngestAdapter())


# Deprecated shim wrapper
async def ingest_rss(task_run_id: str | None = None) -> int:
    """Deprecated: use src.ingest.pipeline.ingest_source instead."""
    from src.ingest.pipeline import ingest_source
    summary = await ingest_source(IngestionSourceType.RSS, task_run_id)
    return summary.saved_count