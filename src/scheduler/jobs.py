from __future__ import annotations

import logging
from datetime import datetime, timezone
import traceback

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update

from src.core.config import settings
from src.storage.database import async_session_factory
from src.models.schema import JobConfig, TaskRun
import inspect

logger = logging.getLogger("news-agent")

scheduler = AsyncIOScheduler()


async def _job_rss_news() -> None:
    logger.info("Starting RSS news ingestion")
    from src.ingest.news_fetcher import ingest_rss
    count = await ingest_rss()
    logger.info("RSS ingestion complete: %d articles saved", count)


async def _job_newsapi() -> None:
    logger.info("Starting NewsAPI ingestion")
    from src.ingest.newsapi_fetcher import ingest_newsapi
    count = await ingest_newsapi()
    logger.info("NewsAPI ingestion complete: %d articles saved", count)


async def _job_jin10() -> None:
    logger.info("Starting jin10 flash news ingestion")
    from src.ingest.jin10_fetcher import ingest_jin10
    count = await ingest_jin10()
    logger.info("jin10 ingestion complete: %d flash items saved", count)


async def _job_earnings() -> None:
    logger.info("Starting earnings data ingestion")
    from src.ingest.earnings_fetcher import ingest_yfinance_earnings
    count = await ingest_yfinance_earnings()
    logger.info("Earnings ingestion complete: %d earnings saved", count)


async def _job_macro() -> None:
    logger.info("Starting macro data ingestion")
    from src.ingest.macro_fetcher import ingest_fred, ingest_akshare
    fred_count = await ingest_fred()
    akshare_count = await ingest_akshare()
    logger.info("Macro ingestion complete: FRED=%d, AKShare=%d", fred_count, akshare_count)


async def _job_dedup() -> None:
    logger.info("Starting deduplication")
    from src.ingest.dedup import deduplicate_news
    stats = await deduplicate_news()
    logger.info("Deduplication complete: %s", stats)


async def _job_analysis(task_run_id: str | None = None) -> None:
    logger.info("Starting analysis pipeline")
    from src.analysis.classifier import run_analysis_pipeline
    # Pass task_run_id down to pipeline
    stats = await run_analysis_pipeline(batch_size=20, task_run_id=task_run_id)
    logger.info("Analysis complete: %s", stats)


async def _job_briefing() -> None:
    logger.info("Starting Daily Briefing generation")
    from src.analysis.briefing import generate_daily_briefing
    briefing = await generate_daily_briefing()
    if briefing:
        logger.info("Daily Briefing generation complete.")
    else:
        logger.info("Daily Briefing generation failed.")


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
        "id": "jin10",
        "name": "jin10 Flash News",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": str(max(5, settings.NEWS_FETCH_INTERVAL_MINUTES // 2)),
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
        "id": "dedup",
        "name": "Deduplication",
        "enabled": True,
        "trigger_type": "interval",
        "schedule_value": "60",
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


async def run_job_wrapper(job_id: str, trigger_type: str = "scheduled") -> None:
    job_funcs = {
        "rss_news": _job_rss_news,
        "newsapi": _job_newsapi,
        "jin10": _job_jin10,
        "earnings": _job_earnings,
        "macro": _job_macro,
        "dedup": _job_dedup,
        "analysis": _job_analysis,
        "briefing": _job_briefing,
    }
    func = job_funcs.get(job_id)
    if not func:
        logger.error(f"Job function for {job_id} not found")
        return

    logger.info(f"Starting run for job: {job_id} ({trigger_type})")
    
    # 1. Initialize TaskRun in DB
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
                await session.execute(
                    update(TaskRun)
                    .where(TaskRun.id == task_run_id)
                    .values(
                        status=status,
                        end_time=datetime.now(timezone.utc),
                        message=message if status == "failed" else None
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
            for config in db_configs:
                default_item = next((d for d in DEFAULT_JOBS if d["id"] == config.id), None)
                if default_item and config.schedule_value != default_item["schedule_value"]:
                    logger.info(f"Syncing schedule for job {config.id} in DB to {default_item['schedule_value']}")
                    config.schedule_value = default_item["schedule_value"]
                    session.add(config)
                    updated_any = True
            if updated_any:
                await session.commit()

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