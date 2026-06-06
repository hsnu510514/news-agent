from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_

from src.analysis.pipeline import process_article_sequentially
from src.models.schema import AnalysisResult, NewsArticle
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


async def run_analysis_pipeline(batch_size: int = 20, urgent_only: bool = False) -> dict:
    stats = {"analyzed": 0, "failed": 0, "skipped": 0}

    async with async_session_factory() as session:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)

        stmt = (
            select(NewsArticle)
            .outerjoin(AnalysisResult, NewsArticle.id == AnalysisResult.article_id)
            .where(AnalysisResult.id.is_(None))
            .where(NewsArticle.is_relevant == True)
            .where(NewsArticle.content.isnot(None))
            .where(NewsArticle.published_at >= cutoff)
            .order_by(NewsArticle.published_at.desc())
            .limit(batch_size)
        )

        if urgent_only:
            stmt = stmt.where(NewsArticle.source_type.in_(["jin10", "newsapi"]))

        articles = (await session.execute(stmt)).scalars().all()

        for article in articles:
            try:
                # Process sequentially
                await process_article_sequentially(article, session)
                stats["analyzed"] += 1
            except Exception:
                stats["failed"] += 1
                logger.exception("Failed to analyze article sequentially: %s", article.id)

        await session.commit()

    logger.info("Analysis pipeline complete: %s", stats)
    return stats