import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.schema import JobConfig, NewsArticle
from src.scheduler.jobs import run_job_wrapper

@pytest.mark.asyncio
async def test_volume_checker_triggers_preprocessing_on_threshold(monkeypatch):
    # We will mock the volume checker logic. It will query the DB for JobConfigs.
    # 1. Arrange: Mock JobConfigs
    mock_config_preprocessing = JobConfig(
        id="preprocessing",
        name="News Pre-processing",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=None,
        cooldown_minutes=5,
        volume_threshold=5, # Threshold is 5 articles
    )
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    
    # Mock execute results
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "job_configs" in stmt_str:
            # Query configs
            res.scalars.return_value.all.return_value = [mock_config_preprocessing]
        elif "task_runs" in stmt_str:
            # Not running
            res.scalars.return_value.all.return_value = []
        elif "count" in stmt_str or "news_articles" in stmt_str:
            # Pending articles count: return 6 (exceeding threshold of 5)
            res.scalar.return_value = 6
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Spy/mock the job trigger run_job_wrapper or the asyncio create_task
    # We want to see if it triggers the preprocessing job
    triggered_jobs = []
    async def mock_run_job_wrapper(job_id, trigger_type, task_run_id=None):
        triggered_jobs.append(job_id)
        return None
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs.run_job_wrapper", mock_run_job_wrapper)
    ):
        # Import and execute volume check function (which will be implemented in green phase)
        from src.scheduler.jobs import _job_volume_check
        
        # 2. Act
        await _job_volume_check()
        import asyncio
        await asyncio.sleep(0.01) # Yield to event loop for background task to execute

        # 3. Assert
        assert "preprocessing" in triggered_jobs


@pytest.mark.asyncio
async def test_volume_checker_does_not_trigger_below_threshold(monkeypatch):
    # 1. Arrange: Mock JobConfigs
    mock_config_preprocessing = JobConfig(
        id="preprocessing",
        name="News Pre-processing",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=None,
        cooldown_minutes=5,
        volume_threshold=5, # Threshold is 5 articles
    )
    
    mock_session = MagicMock(spec=AsyncSession)
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "job_configs" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_config_preprocessing]
        elif "task_runs" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "count" in stmt_str or "news_articles" in stmt_str:
            # Below threshold: only 3 pending articles
            res.scalar.return_value = 3
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    triggered_jobs = []
    async def mock_run_job_wrapper(job_id, trigger_type, task_run_id=None):
        triggered_jobs.append(job_id)
        return None
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs.run_job_wrapper", mock_run_job_wrapper)
    ):
        from src.scheduler.jobs import _job_volume_check
        
        await _job_volume_check()
        import asyncio
        await asyncio.sleep(0.01)
        
        # Assert: preprocessing should NOT be triggered
        assert "preprocessing" not in triggered_jobs


@pytest.mark.asyncio
async def test_volume_checker_skips_during_cooldown(monkeypatch):
    # 1. Arrange: Mock JobConfigs in cooldown
    mock_config_preprocessing = JobConfig(
        id="preprocessing",
        name="News Pre-processing",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=datetime.now(timezone.utc) - timedelta(minutes=2), # Cooldown is 5 mins, run 2 mins ago
        cooldown_minutes=5,
        volume_threshold=5,
    )
    
    mock_session = MagicMock(spec=AsyncSession)
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "job_configs" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_config_preprocessing]
        elif "task_runs" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "count" in stmt_str or "news_articles" in stmt_str:
            # Threshold met, but task is in cooldown
            res.scalar.return_value = 6
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    triggered_jobs = []
    async def mock_run_job_wrapper(job_id, trigger_type, task_run_id=None):
        triggered_jobs.append(job_id)
        return None
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs.run_job_wrapper", mock_run_job_wrapper)
    ):
        from src.scheduler.jobs import _job_volume_check
        
        await _job_volume_check()
        import asyncio
        await asyncio.sleep(0.01)
        
        # Assert: preprocessing should NOT be triggered due to cooldown
        assert "preprocessing" not in triggered_jobs

