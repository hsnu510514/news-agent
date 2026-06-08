from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from src.core.config import settings
from src.models.schema import MarketWire, SourceTypeEnum, LanguageEnum
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")

JIN10_FLASH_URL = "https://flash-api.jin10.com/get_flash_list"
JIN10_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "x-app-id": "5c4a55f4c085",
    "x-version": "1.0.0",
}


async def ingest_jin10() -> int:
    total_saved = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"channel": "-8200", "vip": "1"}
            resp = await client.get(JIN10_FLASH_URL, headers=JIN10_HEADERS, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("Failed to fetch jin10 flash data via API")
            total_saved = await _ingest_jin10_rss(client)
            return total_saved

        flash_list = data.get("data", []) if isinstance(data, dict) else []
        if not flash_list:
            logger.warning("jin10 API returned no data, trying RSS fallback")
            return await _ingest_jin10_rss(client)

    async with async_session_factory() as session:
        for item in flash_list:
            content = item.get("data", {}).get("content", "") or item.get("content", "")
            if not content:
                continue

            content_hash = hashlib.sha256(content.encode()).hexdigest()

            existing = await session.execute(
                select(MarketWire).where(MarketWire.content_hash == content_hash)
            )
            if existing.scalar_one_or_none():
                continue

            published_at = None
            timestamps = item.get("data", {}).get("time") or item.get("time")
            if timestamps:
                try:
                    if isinstance(timestamps, (int, float)):
                        published_at = datetime.fromtimestamp(int(timestamps) / 1000, tz=timezone.utc)
                    else:
                        published_at = datetime.fromisoformat(str(timestamps))
                except Exception:
                    pass

            related_symbols = item.get("data", {}).get("symbols") or item.get("symbols") or []

            flash = MarketWire(
                content=content[:10000],
                content_hash=content_hash,
                source_type=SourceTypeEnum.JIN10,
                language=LanguageEnum.ZH,
                importance=int(item.get("data", {}).get("importance", 0) or item.get("importance", 0) or 0),
                related_symbols=related_symbols,
                published_at=published_at,
                extra=item,
            )
            session.add(flash)
            total_saved += 1

        await session.commit()

    return total_saved


async def _ingest_jin10_rss(client: httpx.AsyncClient) -> int:
    import feedparser

    total_saved = 0
    rss_urls = [
        "https://rsshub.app/jin10/flash",
        "https://rss.jin10.com/flash",
    ]

    for rss_url in rss_urls:
        try:
            resp = await client.get(rss_url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception:
            logger.debug("jin10 RSS feed failed: %s", rss_url)
            continue

        async with async_session_factory() as session:
            for entry in feed.entries:
                content = entry.get("summary", "") or entry.get("title", "")
                if not content:
                    continue

                content_hash = hashlib.sha256(content.encode()).hexdigest()

                existing = await session.execute(
                    select(MarketWire).where(MarketWire.content_hash == content_hash)
                )
                if existing.scalar_one_or_none():
                    continue

                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                flash = MarketWire(
                    content=content[:10000],
                    content_hash=content_hash,
                    source_type=SourceTypeEnum.JIN10,
                    language=LanguageEnum.ZH,
                    importance=0,
                    published_at=published_at,
                    extra={"title": entry.get("title", ""), "link": entry.get("link", "")},
                )
                session.add(flash)
                total_saved += 1

            await session.commit()
        break

    return total_saved