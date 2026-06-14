from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.llm import check_relevance
from src.models.schema import NewsArticle, TaskRun
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


def hash_content(content: str) -> str:
    return hashlib.sha256(content.strip().encode()).hexdigest()


async def run_preprocessing_pipeline(
    batch_size: int | None = None, task_run_id: str | None = None
) -> dict:
    if batch_size is None:
        batch_size = getattr(settings, "PREPROCESSING_BATCH_SIZE", 50)

    stats = {"processed": 0, "duplicates": 0, "relevant": 0, "irrelevant": 0}
    total_count = 0
    
    while True:
        async with async_session_factory() as session:
            # Fetch pending articles (is_relevant is None)
            stmt = (
                select(NewsArticle)
                .where(NewsArticle.is_relevant.is_(None))
                .order_by(NewsArticle.fetched_at.asc())
                .limit(batch_size)
            )
            articles = (await session.execute(stmt)).scalars().all()
            
            if not articles:
                break

            # Update TaskRun total_count if task_run_id provided
            if task_run_id:
                total_count += len(articles)
                try:
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .values(total_count=total_count)
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to update TaskRun total_count for preprocessing")

            batch_aborted = False
            for article in articles:
                # Check for cancellation before processing article
                if task_run_id:
                    try:
                        stmt_status = select(TaskRun.status).where(TaskRun.id == task_run_id)
                        run_status = (await session.execute(stmt_status)).scalar()
                        if run_status != "running":
                            logger.info("Preprocessing task %s was cancelled/stopped", task_run_id)
                            batch_aborted = True
                            break
                    except Exception:
                        logger.exception("Failed to query TaskRun status during preprocessing loop")

                # 1. Compute content hash
                content_hash = None
                if article.content:
                    content_hash = hash_content(article.content)
                    article.content_hash = content_hash

                # 2. Content duplication check
                is_dup = False
                if content_hash:
                    stmt_dup = (
                        select(NewsArticle)
                        .where(
                            NewsArticle.content_hash == content_hash,
                            NewsArticle.id != article.id,
                            NewsArticle.is_relevant.isnot(None),
                        )
                        .order_by(NewsArticle.fetched_at.asc())
                        .limit(1)
                    )
                    original = (await session.execute(stmt_dup)).scalar_one_or_none()
                    if original:
                        article.is_relevant = False
                        article.duplicate_of_id = original.id
                        article.content = None
                        article.summary = None
                        stats["duplicates"] += 1
                        stats["processed"] += 1
                        is_dup = True

                # 3. LLM relevance check
                if not is_dup:
                    try:
                        # Pass title and temporary summary (description) or content
                        text_for_relevance = article.summary or article.content or ""
                        is_relevant = await check_relevance(article.title, text_for_relevance)
                        article.is_relevant = is_relevant
                        
                        if is_relevant:
                            stats["relevant"] += 1
                        else:
                            article.content = None
                            article.summary = None
                            stats["irrelevant"] += 1
                        stats["processed"] += 1
                    except Exception:
                        logger.exception("Failed to check relevance for article %s", article.id)
                        await session.rollback()
                        continue

                # Update metrics in TaskRun
                if task_run_id:
                    try:
                        await session.execute(
                            update(TaskRun)
                            .where(TaskRun.id == task_run_id)
                            .values(
                                processed_count=stats["processed"],
                                failed_count=stats["processed"] - (stats["relevant"] + stats["irrelevant"] + stats["duplicates"])
                            )
                        )
                    except Exception:
                        logger.exception("Failed to update TaskRun progress in loop")

                # Checkpoint: commit per article
                try:
                    await session.commit()
                except Exception:
                    logger.exception("Failed to commit changes for article %s", article.id)
                    await session.rollback()

            if batch_aborted:
                break

    return stats
