from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Sequence
import httpx
from sqlalchemy import select, update
from src.storage.database import async_session_factory
from src.models.schema import TaskRun
from src.ingest.interface import IngestionSourceType, IngestionSummary, BaseIngestAdapter

logger = logging.getLogger("news-agent")

_registry: Dict[IngestionSourceType, BaseIngestAdapter] = {}


def _lazy_load_adapters() -> None:
    try:
        import src.ingest.news_fetcher
        import src.ingest.newsapi_fetcher
        # collector, earnings, and macro will be added as we migrate them
    except ImportError:
        logger.exception("Failed to lazy load adapters")


def register_adapter(source_type: IngestionSourceType, adapter: BaseIngestAdapter) -> None:
    """Registers a concrete adapter instance for the specified source type."""
    _registry[source_type] = adapter
    logger.debug("Registered ingestion adapter for %s", source_type)


def get_adapter(source_type: IngestionSourceType) -> BaseIngestAdapter:
    """Retrieves the adapter for the source type, raising KeyError if not found."""
    if source_type not in _registry:
        _lazy_load_adapters()
    return _registry[source_type]


async def ingest_source(
    source_type: IngestionSourceType, 
    task_run_id: Optional[str] = None
) -> IngestionSummary:
    """Ingests data from a single source channel, managing transactions and logging."""
    start_time = time.time()
    error_msg = None
    fetched_count = 0
    saved_count = 0

    try:
        adapter = get_adapter(source_type)
    except KeyError:
        error_msg = f"No ingestion adapter registered for source: {source_type.value}"
        logger.error(error_msg)
        return IngestionSummary(
            source_type=source_type,
            fetched_count=0,
            saved_count=0,
            duration_seconds=time.time() - start_time,
            error_message=error_msg,
        )

    async with async_session_factory() as session:
        # Check if the active run has been cancelled before starting
        if task_run_id:
            try:
                stmt_status = select(TaskRun.status).where(TaskRun.id == task_run_id)
                run_status = (await session.execute(stmt_status)).scalar()
                if run_status and run_status != "running":
                    logger.info("Ingestion source %s run was cancelled or stopped", source_type.value)
                    return IngestionSummary(
                        source_type=source_type,
                        fetched_count=0,
                        saved_count=0,
                        duration_seconds=time.time() - start_time,
                        error_message="Cancelled",
                    )
            except Exception:
                logger.exception("Failed to query TaskRun status during ingestion start")

        try:
            # We configure follow_redirects=True for flexibility with RSS feeds
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # 1. Fetch raw items from source adapter
                items = await adapter.fetch(client, session)
                fetched_count = len(items)

                # 2. Filter duplicates
                non_duplicates = await adapter.filter_duplicates(items, session)

                # 3. Add new records to session
                for item in non_duplicates:
                    session.add(item)

                # 4. Commit transaction
                await session.commit()
                saved_count = len(non_duplicates)

        except Exception as e:
            logger.exception("Ingestion failed during core loop for source: %s", source_type.value)
            await session.rollback()
            error_msg = str(e)

        # 5. Increment counts in TaskRun database record
        if task_run_id:
            try:
                await session.execute(
                    update(TaskRun)
                    .where(TaskRun.id == task_run_id)
                    .values(
                        processed_count=TaskRun.processed_count + saved_count,
                        total_count=TaskRun.total_count + fetched_count,
                        message=error_msg if error_msg else None,
                    )
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to update TaskRun counts in DB for source %s", source_type.value)

    return IngestionSummary(
        source_type=source_type,
        fetched_count=fetched_count,
        saved_count=saved_count,
        duration_seconds=time.time() - start_time,
        error_message=error_msg,
    )


async def ingest_all(
    task_run_id: Optional[str] = None
) -> Dict[IngestionSourceType, IngestionSummary]:
    """Runs all registered ingestion sources sequentially, accumulating results."""
    summaries: Dict[IngestionSourceType, IngestionSummary] = {}
    
    # Run active/registered sources in stable sequence to avoid lock contention
    for source_type in list(IngestionSourceType):
        if source_type in _registry:
            summary = await ingest_source(source_type, task_run_id=task_run_id)
            summaries[source_type] = summary
            
    return summaries
