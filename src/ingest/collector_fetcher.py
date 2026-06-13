from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.llm import check_relevance
from src.models.schema import LanguageEnum, NewsArticle, SourceTypeEnum, TaskRun
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _detect_language(url: str, source_name: str) -> LanguageEnum:
    # If source name contains Chinese characters, it is Chinese
    if any("\u4e00" <= char <= "\u9fff" for char in source_name):
        return LanguageEnum.ZH
    # Otherwise check url domain signatures
    if any(
        d in url for d in ["36kr", "eastmoney", "sina", "wallstreetcn", "yicai", "caixin"]
    ):
        return LanguageEnum.ZH
    return LanguageEnum.EN


def _normalize_source_name(name: str) -> str:
    name_lower = name.lower()
    if "bloomberg" in name_lower:
        return "Bloomberg"
    if "caixin" in name_lower or "财新" in name:
        return "财新网"
    if "wallstreetcn" in name_lower or "华尔街见闻" in name:
        return "华尔街见闻"
    if "36kr" in name_lower:
        return "36Kr"
    if "yicai" in name_lower or "第一财经" in name:
        return "第一财经"
    if "sina" in name_lower or "新浪财经" in name:
        return "新浪财经"
    return name.strip()


async def ingest_collector(task_run_id: str | None = None) -> int:
    total_saved = 0
    total_fetched = 0
    enabled_sources = [
        s.strip().lower()
        for s in settings.ENABLED_COLLECTOR_SOURCES.split(",")
        if s.strip()
    ]

    async with async_session_factory() as session:
        # 1. Retrieve the latest sync watermark
        stmt = select(func.max(NewsArticle.fetched_at)).where(
            NewsArticle.source_type == SourceTypeEnum.COLLECTOR
        )
        result = await session.execute(stmt)
        last_fetched_at = result.scalar()

        # 2. Query Collector API
        limit = 100
        offset = 0
        
        # Format the base URL and endpoint
        base_url = settings.COLLECTOR_BASE_URL.rstrip("/")
        url = f"{base_url}/api/items"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        if settings.RSSHUB_ACCESS_KEY:
            headers["Authorization"] = f"Bearer {settings.RSSHUB_ACCESS_KEY}"

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            while True:
                params: dict[str, str | int] = {"limit": limit, "offset": offset}
                if last_fetched_at:
                    # ISO 8601 string watermark
                    params["since"] = last_fetched_at.isoformat()

                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                
                if not items:
                    break

                total_fetched += len(items)

                for item in items:
                    raw_source_name = item.get("source_name") or "Collector"
                    if enabled_sources and raw_source_name.strip().lower() not in enabled_sources:
                        logger.info("Skipping disabled Collector source: %s", raw_source_name)
                        continue

                    item_url = item.get("url") or item.get("guid") or ""
                    if not item_url:
                        continue

                    url_hash = _hash_url(item_url)

                    # Check for duplicates
                    existing = await session.execute(
                        select(NewsArticle).where(NewsArticle.url_hash == url_hash)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    title = item.get("title", "").strip()
                    if not title:
                        continue

                    description = item.get("description") or ""
                    content = item.get("content") or description

                    # Normalize source name & language
                    raw_source_name = item.get("source_name") or "Collector"
                    normalized_source_name = _normalize_source_name(raw_source_name)
                    language = _detect_language(item_url, raw_source_name)

                    # Parse timestamps
                    published_at = None
                    published_str = item.get("published_at")
                    if published_str:
                        try:
                            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    fetched_at = datetime.now(timezone.utc)
                    fetched_str = item.get("fetched_at")
                    if fetched_str:
                        try:
                            fetched_at = datetime.fromisoformat(fetched_str.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    article = NewsArticle(
                        url=item_url,
                        url_hash=url_hash,
                        source_type=SourceTypeEnum.COLLECTOR,
                        source_name=normalized_source_name,
                        language=language,
                        title=title,
                        content=content[:50000] if content else None,
                        content_hash=None,
                        summary=description,
                        published_at=published_at,
                        fetched_at=fetched_at,
                        extra={
                            "collector_id": item.get("id"),
                            "collector_source_id": item.get("source_id"),
                            "author": item.get("author", ""),
                            "categories": item.get("categories", []),
                        },
                        is_relevant=None,
                    )
                    session.add(article)
                    total_saved += 1

                await session.commit()

                # If we received fewer items than the limit, we've reached the end
                if len(items) < limit:
                    break
                offset += limit

        if task_run_id:
            try:
                await session.execute(
                    update(TaskRun)
                    .where(TaskRun.id == task_run_id)
                    .values(processed_count=total_saved, total_count=total_fetched)
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to update TaskRun metrics for Collector sync")

    return total_saved
