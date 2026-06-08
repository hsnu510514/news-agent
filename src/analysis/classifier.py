import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_

from src.analysis.pipeline import process_article_sequentially
from src.models.schema import AnalysisResult, NewsArticle
from src.storage.database import async_session_factory
from src.core.llm import DailyQuotaExhaustedError

logger = logging.getLogger("news-agent")

_pipeline_lock = asyncio.Lock()


async def run_analysis_pipeline(batch_size: int = 20, urgent_only: bool = False, task_run_id: str | None = None) -> dict:
    if _pipeline_lock.locked():
        logger.info("Analysis pipeline is already running. Skipping this run.")
        return {"analyzed": 0, "failed": 0, "skipped": 0, "reason": "already_running"}

    async with _pipeline_lock:
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

            if task_run_id and len(articles) > 0:
                from src.models.schema import TaskRun
                from sqlalchemy import update
                try:
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .values(total_count=len(articles))
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to update TaskRun total_count")

            for article in articles:
                try:
                    # Process sequentially
                    await process_article_sequentially(article, session)
                    stats["analyzed"] += 1
                    if task_run_id:
                        from src.models.schema import TaskRun
                        from sqlalchemy import update
                        await session.execute(
                            update(TaskRun)
                            .where(TaskRun.id == task_run_id)
                            .values(
                                processed_count=stats["analyzed"],
                                failed_count=stats["failed"]
                            )
                        )
                    # Commit per article (checkpointing)
                    await session.commit()
                except DailyQuotaExhaustedError as e:
                    stats["failed"] += 1
                    try:
                        await session.rollback()
                        if task_run_id:
                            from src.models.schema import TaskRun
                            from sqlalchemy import update
                            await session.execute(
                                update(TaskRun)
                                .where(TaskRun.id == task_run_id)
                                .values(
                                    processed_count=stats["analyzed"],
                                    failed_count=stats["failed"]
                                )
                            )
                            await session.commit()
                    except Exception:
                        logger.exception("Failed to update TaskRun status on quota abort")
                    logger.error("Daily API quota exhausted. Aborting analysis pipeline run early. Error: %s", e)
                    break
                except Exception:
                    stats["failed"] += 1
                    try:
                        await session.rollback()
                        if task_run_id:
                            from src.models.schema import TaskRun
                            from sqlalchemy import update
                            await session.execute(
                                update(TaskRun)
                                .where(TaskRun.id == task_run_id)
                                .values(
                                    processed_count=stats["analyzed"],
                                    failed_count=stats["failed"]
                                )
                            )
                            await session.commit()
                    except Exception:
                        logger.exception("Failed to update TaskRun status on error")
                    logger.exception("Failed to analyze article sequentially: %s", article.id)

        logger.info("Analysis pipeline complete: %s", stats)
        return stats