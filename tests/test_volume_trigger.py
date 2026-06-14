import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.schema import JobConfig, TaskRun
from src.scheduler.jobs import run_job_wrapper

@pytest.mark.asyncio
async def test_chained_triggering_success():
    # Arrange: mock JobConfig objects
    rss_config = JobConfig(
        id="rss_news",
        name="RSS News Fetch",
        enabled=True,
        trigger_type="interval",
        schedule_value="15",
        last_run_time=None,
        cooldown_minutes=5,
    )
    prep_config = JobConfig(
        id="preprocessing",
        name="News Pre-processing",
        enabled=True,
        trigger_type="interval",
        schedule_value="5",
        last_run_time=None,
        cooldown_minutes=5,
    )
    analysis_config = JobConfig(
        id="analysis",
        name="AI Analysis",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=None,
        cooldown_minutes=5,
    )

    configs_db = {
        "rss_news": rss_config,
        "preprocessing": prep_config,
        "analysis": analysis_config,
    }

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        
        job_id = None
        try:
            params = stmt.compile().params
            for val in params.values():
                if isinstance(val, str) and val in configs_db:
                    job_id = val
                    break
        except Exception:
            pass

        if not job_id:
            for jid in configs_db:
                if f"'{jid}'" in stmt_str or f'"{jid}"' in stmt_str:
                    job_id = jid
                    break

        if "job_configs" in stmt_str:
            if job_id:
                res.scalar_one_or_none.return_value = configs_db[job_id]
            else:
                res.scalars.return_value.all.return_value = list(configs_db.values())
        elif "task_runs" in stmt_str:
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # Mock job functions
    mock_rss = AsyncMock()
    mock_prep = AsyncMock()
    mock_analysis = AsyncMock()

    created_tasks = []
    original_create_task = asyncio.create_task
    def spy_create_task(coro, *args, **kwargs):
        t = original_create_task(coro, *args, **kwargs)
        created_tasks.append(t)
        return t

    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_rss_news", mock_rss),
        patch("src.scheduler.jobs._job_preprocessing", mock_prep),
        patch("src.scheduler.jobs._job_analysis", mock_analysis),
        patch("asyncio.create_task", spy_create_task),
    ):
        # Act: Run RSS news fetch
        await run_job_wrapper("rss_news", "scheduled")
        
        # Loop to await all background tasks, including nested ones
        while created_tasks:
            current_tasks = list(created_tasks)
            created_tasks.clear()
            await asyncio.gather(*current_tasks, return_exceptions=True)
            await asyncio.sleep(0.01)

        # Assert: verify that all job functions were called in sequence
        mock_rss.assert_called_once()
        mock_prep.assert_called_once()
        mock_analysis.assert_called_once()


@pytest.mark.asyncio
async def test_chained_triggering_skips_when_disabled():
    # Arrange: preprocessing is disabled
    rss_config = JobConfig(
        id="rss_news", name="RSS News Fetch", enabled=True, last_run_time=None, cooldown_minutes=5
    )
    prep_config = JobConfig(
        id="preprocessing", name="News Pre-processing", enabled=False, last_run_time=None, cooldown_minutes=5
    )
    analysis_config = JobConfig(
        id="analysis", name="AI Analysis", enabled=True, last_run_time=None, cooldown_minutes=5
    )

    configs_db = {
        "rss_news": rss_config,
        "preprocessing": prep_config,
        "analysis": analysis_config,
    }

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        
        job_id = None
        try:
            params = stmt.compile().params
            for val in params.values():
                if isinstance(val, str) and val in configs_db:
                    job_id = val
                    break
        except Exception:
            pass

        if not job_id:
            for jid in configs_db:
                if f"'{jid}'" in stmt_str or f'"{jid}"' in stmt_str:
                    job_id = jid
                    break

        if "job_configs" in stmt_str:
            if job_id:
                res.scalar_one_or_none.return_value = configs_db[job_id]
            else:
                res.scalars.return_value.all.return_value = list(configs_db.values())
        elif "task_runs" in stmt_str:
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_rss = AsyncMock()
    mock_prep = AsyncMock()
    mock_analysis = AsyncMock()

    created_tasks = []
    original_create_task = asyncio.create_task
    def spy_create_task(coro, *args, **kwargs):
        t = original_create_task(coro, *args, **kwargs)
        created_tasks.append(t)
        return t

    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_rss_news", mock_rss),
        patch("src.scheduler.jobs._job_preprocessing", mock_prep),
        patch("src.scheduler.jobs._job_analysis", mock_analysis),
        patch("asyncio.create_task", spy_create_task),
    ):
        await run_job_wrapper("rss_news", "scheduled")
        
        while created_tasks:
            current_tasks = list(created_tasks)
            created_tasks.clear()
            await asyncio.gather(*current_tasks, return_exceptions=True)
            await asyncio.sleep(0.01)

        # RSS completes, triggers preprocessing, but preprocessing is disabled so it shouldn't execute
        mock_rss.assert_called_once()
        mock_prep.assert_not_called()


@pytest.mark.asyncio
async def test_chained_triggering_skips_during_cooldown():
    # Arrange: preprocessing ran 2 minutes ago (cooldown is 5 minutes)
    rss_config = JobConfig(
        id="rss_news", name="RSS News Fetch", enabled=True, last_run_time=None, cooldown_minutes=5
    )
    prep_config = JobConfig(
        id="preprocessing",
        name="News Pre-processing",
        enabled=True,
        last_run_time=datetime.now(timezone.utc) - timedelta(minutes=2),
        cooldown_minutes=5,
    )

    configs_db = {
        "rss_news": rss_config,
        "preprocessing": prep_config,
    }

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        
        job_id = None
        try:
            params = stmt.compile().params
            for val in params.values():
                if isinstance(val, str) and val in configs_db:
                    job_id = val
                    break
        except Exception:
            pass

        if not job_id:
            for jid in configs_db:
                if f"'{jid}'" in stmt_str or f'"{jid}"' in stmt_str:
                    job_id = jid
                    break

        if "job_configs" in stmt_str:
            if job_id:
                res.scalar_one_or_none.return_value = configs_db[job_id]
            else:
                res.scalars.return_value.all.return_value = list(configs_db.values())
        elif "task_runs" in stmt_str:
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_rss = AsyncMock()
    mock_prep = AsyncMock()
    mock_analysis = AsyncMock()

    created_tasks = []
    original_create_task = asyncio.create_task
    def spy_create_task(coro, *args, **kwargs):
        t = original_create_task(coro, *args, **kwargs)
        created_tasks.append(t)
        return t

    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_rss_news", mock_rss),
        patch("src.scheduler.jobs._job_preprocessing", mock_prep),
        patch("src.scheduler.jobs._job_analysis", mock_analysis),
        patch("asyncio.create_task", spy_create_task),
    ):
        await run_job_wrapper("rss_news", "scheduled")
        
        while created_tasks:
            current_tasks = list(created_tasks)
            created_tasks.clear()
            await asyncio.gather(*current_tasks, return_exceptions=True)
            await asyncio.sleep(0.01)

        # RSS completes, triggers preprocessing, but preprocessing is in cooldown so it should be skipped
        mock_rss.assert_called_once()
        mock_prep.assert_not_called()
