from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func

from src.models.schema import NewsArticle, MarketWire
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


def hash_content(content: str) -> str:
    return hashlib.sha256(content.strip().encode()).hexdigest()


async def deduplicate_news() -> dict:
    stats = {"duplicates_removed": 0, "content_deduped": 0}
    async with async_session_factory() as session:
        stmt = (
            select(NewsArticle.url_hash, func.count(NewsArticle.id))
            .group_by(NewsArticle.url_hash)
            .having(func.count(NewsArticle.id) > 1)
        )
        result = await session.execute(stmt)
        duplicates = result.all()

        for url_hash, count in duplicates:
            articles = (
                await session.execute(
                    select(NewsArticle)
                    .where(NewsArticle.url_hash == url_hash)
                    .order_by(NewsArticle.fetched_at.asc())
                )
            ).scalars().all()

            for article in articles[1:]:
                article.duplicate_of_id = articles[0].id
                article.is_relevant = False
                stats["duplicates_removed"] += 1

        content_stmt = (
            select(NewsArticle.content_hash, func.count(NewsArticle.id))
            .where(NewsArticle.content_hash.isnot(None))
            .group_by(NewsArticle.content_hash)
            .having(func.count(NewsArticle.id) > 1)
        )
        content_result = await session.execute(content_stmt)
        content_dups = content_result.all()

        for content_hash, count in content_dups:
            articles = (
                await session.execute(
                    select(NewsArticle)
                    .where(NewsArticle.content_hash == content_hash)
                    .order_by(NewsArticle.fetched_at.asc())
                )
            ).scalars().all()

            for article in articles[1:]:
                article.duplicate_of_id = articles[0].id
                article.is_relevant = False
                stats["content_deduped"] += 1

        await session.commit()

    logger.info(
        "Deduplication complete: %d URL duplicates, %d content duplicates removed",
        stats["duplicates_removed"],
        stats["content_deduped"],
    )
    return stats