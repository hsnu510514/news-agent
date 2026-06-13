import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_

from src.analysis.pipeline import process_article_sequentially
from src.models.schema import AnalysisResult, NewsArticle
from src.storage.database import async_session_factory
from src.core.llm import DailyQuotaExhaustedError
from src.core.config import settings

logger = logging.getLogger("news-agent")

_pipeline_lock = asyncio.Lock()


async def run_analysis_pipeline(batch_size: int | None = None, urgent_only: bool = False, task_run_id: str | None = None) -> dict:
    if _pipeline_lock.locked():
        logger.info("Analysis pipeline is already running. Skipping this run.")
        return {"analyzed": 0, "failed": 0, "skipped": 0, "reason": "already_running"}

    if batch_size is None:
        batch_size = getattr(settings, "ANALYSIS_BATCH_SIZE", 20)

    async with _pipeline_lock:
        stats = {"analyzed": 0, "failed": 0, "skipped": 0}
        start_time = datetime.now(timezone.utc)
        status = "success"
        total_count = 0

        while True:
            # Check timeout before starting next batch
            elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60.0
            if elapsed_minutes >= settings.MAX_ANALYSIS_DURATION_MINUTES:
                logger.info(
                    "Analysis pipeline reached execution limit of %d minutes. Timeout.",
                    settings.MAX_ANALYSIS_DURATION_MINUTES
                )
                status = "timeout"
                break

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
                    stmt = stmt.where(NewsArticle.source_type == "newsapi")

                articles = (await session.execute(stmt)).scalars().all()
                if not articles:
                    break

                if task_run_id:
                    from src.models.schema import TaskRun
                    from sqlalchemy import update
                    total_count += len(articles)
                    try:
                        await session.execute(
                            update(TaskRun)
                            .where(TaskRun.id == task_run_id)
                            .values(total_count=total_count)
                        )
                        await session.commit()
                    except Exception:
                        logger.exception("Failed to update TaskRun total_count")

                batch_aborted = False
                for article in articles:
                    # Check cancellation before processing article
                    if task_run_id:
                        try:
                            from src.models.schema import TaskRun
                            stmt_status = select(TaskRun.status).where(TaskRun.id == task_run_id)
                            run_status = (await session.execute(stmt_status)).scalar()
                            if run_status != "running":
                                logger.info("Analysis pipeline run %s was cancelled/stopped", task_run_id)
                                status = "failed"
                                batch_aborted = True
                                break
                        except Exception:
                            logger.exception("Failed to query TaskRun status during analysis loop")

                    # Check timeout before processing each article
                    elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60.0
                    if elapsed_minutes >= settings.MAX_ANALYSIS_DURATION_MINUTES:
                        logger.info(
                            "Analysis pipeline reached execution limit of %d minutes. Timeout.",
                            settings.MAX_ANALYSIS_DURATION_MINUTES
                        )
                        status = "timeout"
                        batch_aborted = True
                        break

                    # Check queue quota status
                    from src.core.llm import llm_queue
                    if getattr(llm_queue, "_quota_exhausted", False):
                        logger.warning("Aborting pipeline early due to LLM queue quota exhaustion.")
                        status = "failed"
                        batch_aborted = True
                        break

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
                        status = "failed"
                        batch_aborted = True
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

                if batch_aborted:
                    break

        if task_run_id and status == "timeout":
            async with async_session_factory() as session:
                from src.models.schema import TaskRun
                from sqlalchemy import update
                try:
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .values(
                            status="timeout",
                            end_time=datetime.now(timezone.utc),
                            message=f"Stopped due to execution time limit ({settings.MAX_ANALYSIS_DURATION_MINUTES} minutes)."
                        )
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to set final TaskRun timeout status")

        # Trigger divergence scan after analysis run if new data was processed
        if stats["analyzed"] > 0:
            try:
                logger.info("Running divergence scan after analysis batch completion")
                async with async_session_factory() as session:
                    from src.analysis.divergence import scan_for_duplicates
                    await scan_for_duplicates(session)
            except Exception:
                logger.exception("Failed to run divergence scan after analysis pipeline")

        stats["status"] = status
        logger.info("Analysis pipeline complete: %s", stats)
        return stats