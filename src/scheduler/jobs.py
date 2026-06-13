from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update, func

from src.core.config import settings
from src.storage.database import async_session_factory
from src.models.schema import JobConfig, TaskRun, NewsArticle, AnalysisResult
import inspect

logger = logging.getLogger("news-agent")

scheduler = AsyncIOScheduler()


async def _job_rss_news(task_run_id: str | None = None) -> None:
    logger.info("Starting RSS news ingestion")
    from src.ingest.pipeline import ingest_source
    from src.ingest.interface import IngestionSourceType
    summary = await ingest_source(IngestionSourceType.RSS, task_run_id=task_run_id)
    logger.info("RSS ingestion complete: %d articles saved", summary.saved_count)


async def _job_newsapi(task_run_id: str | None = None) -> None:
    logger.info("Starting NewsAPI ingestion")
    from src.ingest.pipeline import ingest_source
    from src.ingest.interface import IngestionSourceType
    summary = await ingest_source(IngestionSourceType.NEWSAPI, task_run_id=task_run_id)
    logger.info("NewsAPI ingestion complete: %d articles saved", summary.saved_count)


async def _job_collector(task_run_id: str | None = None) -> None:
    logger.info("Starting Collector news ingestion")
    from src.ingest.collector_fetcher import ingest_collector
    count = await ingest_collector(task_run_id=task_run_id)
    logger.info("Collector ingestion complete: %d articles saved", count)


async def _job_earnings(task_run_id: str | None = None) -> None:
    logger.info("Starting earnings data ingestion")
    from src.ingest.earnings_fetcher import ingest_yfinance_earnings
    count = await ingest_yfinance_earnings()
    logger.info("Earnings ingestion complete: %d earnings saved", count)
    if task_run_id:
        async with async_session_factory() as session:
            await session.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .values(processed_count=count, total_count=count)
            )
            await session.commit()


async def _job_macro(task_run_id: str | None = None) -> None:
    logger.info("Starting macro data ingestion")
    from src.ingest.macro_fetcher import ingest_fred, ingest_akshare
    fred_count = await ingest_fred()
    akshare_count = await ingest_akshare()
    logger.info("Macro ingestion complete: FRED=%d, AKShare=%d", fred_count, akshare_count)
    if task_run_id:
        async with async_session_factory() as session:
            total = fred_count + akshare_count
            await session.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .values(processed_count=total, total_count=total)
            )
            await session.commit()



async def _job_preprocessing(task_run_id: str | None = None) -> None:
    logger.info("Starting news pre-processing pipeline")
    from src.ingest.preprocessing import run_preprocessing_pipeline
    stats = await run_preprocessing_pipeline(task_run_id=task_run_id)
    logger.info("News pre-processing complete: %s", stats)


async def _job_analysis(task_run_id: str | None = None) -> None:
    logger.info("Starting analysis pipeline")
    from src.analysis.classifier import run_analysis_pipeline
    # Pass task_run_id down to pipeline (passing None uses dynamic config setting)
    stats = await run_analysis_pipeline(batch_size=None, task_run_id=task_run_id)
    logger.info("Analysis complete: %s", stats)


async def _job_briefing(task_run_id: str | None = None) -> None:
    logger.info("Starting Daily Briefing generation")
    from src.analysis.briefing import generate_daily_briefing
    briefing = await generate_daily_briefing()
    status = 1 if briefing else 0
    if briefing:
        logger.info("Daily Briefing generation complete.")
    else:
        logger.error("Daily Briefing generation failed.")
        raise RuntimeError("Daily Briefing generation failed. Check logs for details.")
    if task_run_id:
        async with async_session_factory() as session:
            await session.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .values(processed_count=status, total_count=1)
            )
            await session.commit()


async def _job_divergence(task_run_id: str | None = None) -> None:
    logger.info("Starting Divergence Monitor duplicate scan")
    from src.analysis.divergence import scan_for_duplicates
    async with async_session_factory() as session:
        stats = await scan_for_duplicates(session)
        logger.info("Divergence Monitor scan complete: %s", stats)
        if task_run_id:
            found = stats.get("subjects_duplicates_found", 0) + stats.get("insights_duplicates_found", 0)
            scanned = stats.get("subjects_scanned", 0) + stats.get("insights_scanned", 0)
            await session.execute(
                update(TaskRun)
                .where(TaskRun.id == task_run_id)
                .values(processed_count=found, total_count=scanned)
            )
            await session.commit()


async def _job_volume_check() -> None:
    logger.debug("Running volume trigger checks")
    async with async_session_factory() as session:
        try:
            # 1. Fetch enabled configs that have volume threshold
            stmt_configs = select(JobConfig).where(
                JobConfig.enabled == True,
                JobConfig.volume_threshold.isnot(None),
                JobConfig.volume_threshold > 0
            )
            configs = (await session.execute(stmt_configs)).scalars().all()
            if not configs:
                return

            for config in configs:
                # 2. Check if already running
                stmt_running = select(TaskRun).where(
                    TaskRun.job_id == config.id,
                    TaskRun.status == "running"
                )
                running_runs = (await session.execute(stmt_running)).scalars().all()
                if running_runs and isinstance(running_runs, list):
                    continue

                # 3. Check cooldown
                if config.last_run_time:
                    cooldown = config.cooldown_minutes or 5
                    elapsed = datetime.now(timezone.utc) - config.last_run_time
                    if elapsed < timedelta(minutes=cooldown):
                        continue

                # 4. Count pending volume
                pending_count = 0
                if config.id == "preprocessing":
                    stmt_count = select(func.count()).select_from(NewsArticle).where(NewsArticle.is_relevant.is_(None))
                    pending_count = (await session.execute(stmt_count)).scalar() or 0
                elif config.id == "analysis":
                    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                    stmt_count = (
                        select(func.count())
                        .select_from(NewsArticle)
                        .outerjoin(AnalysisResult, NewsArticle.id == AnalysisResult.article_id)
                        .where(AnalysisResult.id.is_(None))
                        .where(NewsArticle.is_relevant == True)
                        .where(NewsArticle.content.isnot(None))
                        .where(NewsArticle.published_at >= cutoff)
                    )
                    pending_count = (await session.execute(stmt_count)).scalar() or 0

                # 5. Trigger if threshold met
                if pending_count >= config.volume_threshold:
                    logger.info(f"Volume trigger threshold met for job {config.id} (Backlog: {pending_count} >= {config.volume_threshold}). Triggering task.")
                    import asyncio
                    asyncio.create_task(run_job_wrapper(config.id, trigger_type="volume"))
        except Exception:
            logger.exception("Error running volume check task")


DEFAULT_JOBS = [
    {
        "id": "rss_news",
        "name": "RSS News Fetch",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(settings.NEWS_FETCH_INTERVAL_MINUTES),
    },
    {
        "id": "newsapi",
        "name": "NewsAPI Fetch",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(settings.NEWSAPI_FETCH_INTERVAL_MINUTES),
    },
    {
        "id": "collector_news",
        "name": "Collector Ingest",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(settings.COLLECTOR_FETCH_INTERVAL_MINUTES),
    },
    {
        "id": "earnings",
        "name": "Earnings Data",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(settings.EARNINGS_FETCH_INTERVAL_HOURS),
    },
    {
        "id": "macro",
        "name": "Macro Indicators",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(settings.MACRO_FETCH_INTERVAL_HOURS),
    },
    {
        "id": "preprocessing",
        "name": "News Pre-processing",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(max(5, settings.NEWS_FETCH_INTERVAL_MINUTES)),
    },
    {
        "id": "analysis",
        "name": "AI Analysis",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(max(10, settings.NEWS_FETCH_INTERVAL_MINUTES)),
    },
    {
        "id": "briefing",
        "name": "Daily Briefing",
        "enabled": True,
        "trigger_type": "cron",
        "schedule_value": "0 7 * * *",
    },
    {
        "id": "divergence",
        "name": "Divergence Monitor Scan",
        "enabled": True,
        "trigger_type": "cron",
        "schedule_value": "0 2 * * *",
    },
    {
        "id": "volume_check",
        "name": "Volume Trigger Checker",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": "1",
    },
]



def _create_trigger(job_id: str, trigger_type: str, schedule_value: str):
    if trigger_type == "cron":
        return CronTrigger.from_crontab(schedule_value)
    elif trigger_type == "interval":
        val = int(schedule_value)
        if job_id in ("earnings", "macro"):
            return IntervalTrigger(hours=val)
        else:
            return IntervalTrigger(minutes=val)
    else:
        raise ValueError(f"Invalid trigger type: {trigger_type}")


async def run_job_wrapper(job_id: str, trigger_type: str = "scheduled", task_run_id: str | None = None) -> None:
    job_funcs = {
        "rss_news": _job_rss_news,
        "newsapi": _job_newsapi,
        "collector_news": _job_collector,
        "earnings": _job_earnings,
        "macro": _job_macro,
        "preprocessing": _job_preprocessing,
        "analysis": _job_analysis,
        "briefing": _job_briefing,
        "divergence": _job_divergence,
        "volume_check": _job_volume_check,
    }

    func = job_funcs.get(job_id)
    if not func:
        logger.error(f"Job function for {job_id} not found")
        return

    logger.info(f"Starting run for job: {job_id} ({trigger_type})")

    # 0. Check if job is already running or in cooldown break
    async with async_session_factory() as session:
        try:
            # Check if running
            stmt_running = select(TaskRun).where(
                TaskRun.job_id == job_id,
                TaskRun.status == "running"
            )
            if task_run_id:
                stmt_running = stmt_running.where(TaskRun.id != task_run_id)
            running_runs = (await session.execute(stmt_running)).scalars().all()
            if running_runs and isinstance(running_runs, list):
                logger.info(f"Job {job_id} is already running. Skipping this execution.")
                if task_run_id:
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .values(
                            status="failed",
                            end_time=datetime.now(timezone.utc),
                            message="Skipped: Job is already running."
                        )
                    )
                    await session.commit()
                return

            # Check cooldown break
            if trigger_type != "manual":
                stmt_config = select(JobConfig).where(JobConfig.id == job_id)
                config = (await session.execute(stmt_config)).scalar_one_or_none()
                if config and isinstance(config, JobConfig) and isinstance(config.last_run_time, datetime):
                    cooldown = config.cooldown_minutes or 5
                    elapsed = datetime.now(timezone.utc) - config.last_run_time
                    if elapsed < timedelta(minutes=cooldown):
                        logger.info(f"Job {job_id} is in cooldown break. Skipping this execution.")
                        if task_run_id:
                            await session.execute(
                                update(TaskRun)
                                .where(TaskRun.id == task_run_id)
                                .values(
                                    status="failed",
                                    end_time=datetime.now(timezone.utc),
                                    message="Skipped: Job is in cooldown break."
                                )
                            )
                            await session.commit()
                        return
        except Exception:
            logger.exception(f"Failed to check running/cooldown status for job {job_id}")
    
    # 1. Initialize TaskRun in DB if not already done
    if not task_run_id:
        import uuid
        task_name = job_id
        task_run_id = str(uuid.uuid4())
        async with async_session_factory() as session:
            try:
                result = await session.execute(select(JobConfig).where(JobConfig.id == job_id))
                config = result.scalar_one_or_none()
                if config:
                    task_name = config.name
                
                task_run = TaskRun(
                    id=task_run_id,
                    job_id=job_id,
                    task_name=task_name,
                    trigger_type=trigger_type,
                    status="running",
                    start_time=datetime.now(timezone.utc),
                )
                session.add(task_run)
                await session.commit()
            except Exception:
                logger.exception(f"Failed to initialize TaskRun in DB for {job_id}")


    status = "success"
    message = ""
    try:
        sig = inspect.signature(func)
        if "task_run_id" in sig.parameters:
            await func(task_run_id=task_run_id)
        else:
            await func()
    except Exception as e:
        status = "failed"
        message = traceback.format_exc()
        logger.exception(f"Job {job_id} failed during execution")

    async with async_session_factory() as session:
        try:
            if task_run_id:
                stmt_run = select(TaskRun).where(TaskRun.id == task_run_id)
                run_obj = (await session.execute(stmt_run)).scalar_one_or_none()
                if run_obj and run_obj.status == "timeout":
                    status = "timeout"

            await session.execute(
                update(JobConfig)
                .where(JobConfig.id == job_id)
                .values(
                    last_run_time=datetime.now(timezone.utc),
                    last_run_status=status,
                    last_run_message=message
                )
            )
            
            if task_run_id:
                if status == "failed":
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .values(
                            status="failed",
                            end_time=datetime.now(timezone.utc),
                            message=message
                        )
                    )
                else:
                    # Only mark as success if it is still running (prevent overwriting timeout status)
                    await session.execute(
                        update(TaskRun)
                        .where(TaskRun.id == task_run_id)
                        .where(TaskRun.status == "running")
                        .values(
                            status="success",
                            end_time=datetime.now(timezone.utc)
                        )
                    )
            await session.commit()
        except Exception:
            logger.exception(f"Failed to update final job/task status in DB for {job_id}")



def reschedule_job_in_scheduler(config: JobConfig) -> None:
    if scheduler.get_job(config.id):
        scheduler.remove_job(config.id)

    if config.enabled:
        try:
            trigger = _create_trigger(config.id, config.trigger_type, config.schedule_value)
            scheduler.add_job(
                run_job_wrapper,
                trigger,
                id=config.id,
                name=config.name,
                args=[config.id],
                replace_existing=True,
            )
            logger.info(f"Successfully rescheduled job {config.id} in active scheduler")
        except Exception as e:
            logger.error(f"Failed to reschedule job {config.id}: {e}")


async def setup_jobs() -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(JobConfig))
        db_configs = result.scalars().all()

        if not db_configs:
            logger.info("No job configs found in database. Seeding defaults...")
            db_configs = []
            for d in DEFAULT_JOBS:
                config = JobConfig(
                    id=d["id"],
                    name=d["name"],
                    enabled=d["enabled"],
                    trigger_type=d["trigger_type"],
                    schedule_value=d["schedule_value"]
                )
                session.add(config)
                db_configs.append(config)
            await session.commit()
        else:
            # Sync schedule value from settings if default job configs changed in code
            updated_any = False
            db_job_ids = {config.id for config in db_configs}
            for d in DEFAULT_JOBS:
                if d["id"] not in db_job_ids:
                    logger.info(f"Seeding missing default job config {d['id']} to database")
                    config = JobConfig(
                        id=d["id"],
                        name=d["name"],
                        enabled=d["enabled"],
                        trigger_type=d["trigger_type"],
                        schedule_value=d["schedule_value"]
                    )
                    session.add(config)
                    updated_any = True

            for config in db_configs:
                default_item = next((d for d in DEFAULT_JOBS if d["id"] == config.id), None)
                if default_item and config.schedule_value != default_item["schedule_value"]:
                    logger.info(f"Syncing schedule for job {config.id} in DB to {default_item['schedule_value']}")
                    config.schedule_value = default_item["schedule_value"]
                    session.add(config)
                    updated_any = True
            if updated_any:
                await session.commit()


            # Clean up/delete any deprecated jobs from the database (e.g. jin10)
            default_ids = {d["id"] for d in DEFAULT_JOBS}
            deleted_any = False
            for config in list(db_configs):
                if config.id not in default_ids:
                    logger.info(f"Deleting outdated job config {config.id} from database")
                    await session.delete(config)
                    deleted_any = True
            if deleted_any:
                await session.commit()
                # Re-fetch db_configs
                result = await session.execute(select(JobConfig))
                db_configs = result.scalars().all()

        for config in db_configs:
            if config.enabled:
                try:
                    trigger = _create_trigger(config.id, config.trigger_type, config.schedule_value)
                    scheduler.add_job(
                        run_job_wrapper,
                        trigger,
                        id=config.id,
                        name=config.name,
                        args=[config.id],
                        replace_existing=True,
                    )
                    logger.info(f"Scheduled job: {config.name} ({config.trigger_type}: {config.schedule_value})")
                except Exception:
                    logger.exception(f"Failed to schedule job {config.name} on startup")


async def start_scheduler() -> None:
    if settings.SCHEDULER_ENABLED:
        if scheduler.running:
            logger.info("Scheduler is already running")
            return
        await setup_jobs()
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")