import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.schema import JobConfig
from src.scheduler.jobs import run_job_wrapper

@pytest.mark.asyncio
async def test_run_job_wrapper_skips_during_cooldown(monkeypatch):
    # 1. Arrange: Create a mock JobConfig in cooldown
    job_id = "analysis"
    cooldown_minutes = 5
    last_run_time = datetime.now(timezone.utc) - timedelta(minutes=2) # 2 minutes ago, which is < 5 mins cooldown
    
    # Create mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    
    mock_job_config = JobConfig(
        id=job_id,
        name="AI Analysis",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=last_run_time,
        cooldown_minutes=cooldown_minutes,
        volume_threshold=None,
    )
    
    # Mock different query results
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "task_runs" in stmt_str:
            # Not running
            res.scalars.return_value.all.return_value = []
        else:
            # Return JobConfig
            res.scalar_one_or_none.return_value = mock_job_config
            res.scalars.return_value.all.return_value = [mock_job_config]
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock the actual job function to verify if it is called or skipped
    mock_job_func = AsyncMock()
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_analysis", mock_job_func)
    ):
        # 2. Act: Execute wrapper
        await run_job_wrapper(job_id=job_id, trigger_type="scheduled")
        
        # 3. Assert: Check that the actual job function was NOT called
        mock_job_func.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_wrapper_allows_manual_during_cooldown(monkeypatch):
    # 1. Arrange: Create a mock JobConfig in cooldown
    job_id = "analysis"
    cooldown_minutes = 5
    last_run_time = datetime.now(timezone.utc) - timedelta(minutes=2) # In cooldown
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    
    mock_job_config = JobConfig(
        id=job_id,
        name="AI Analysis",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=last_run_time,
        cooldown_minutes=cooldown_minutes,
        volume_threshold=None,
    )
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "task_runs" in stmt_str:
            # Not running
            res.scalars.return_value.all.return_value = []
        else:
            # Return JobConfig
            res.scalar_one_or_none.return_value = mock_job_config
            res.scalars.return_value.all.return_value = [mock_job_config]
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    mock_job_func = AsyncMock()
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_analysis", mock_job_func)
    ):
        # 2. Act: Execute wrapper with trigger_type="manual"
        await run_job_wrapper(job_id=job_id, trigger_type="manual")
        
        # 3. Assert: Check that the actual job function WAS called
        mock_job_func.assert_called_once()


@pytest.mark.asyncio
async def test_run_job_wrapper_blocks_if_already_running(monkeypatch):
    # 1. Arrange: Create a mock JobConfig not in cooldown
    job_id = "analysis"
    cooldown_minutes = 5
    last_run_time = datetime.now(timezone.utc) - timedelta(minutes=10) # Out of cooldown
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    
    mock_job_config = JobConfig(
        id=job_id,
        name="AI Analysis",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=last_run_time,
        cooldown_minutes=cooldown_minutes,
        volume_threshold=None,
    )
    
    # We will simulate a running TaskRun being returned
    from src.models.schema import TaskRun
    mock_running_run = TaskRun(
        id="some-active-run-id",
        job_id=job_id,
        task_name="AI Analysis",
        status="running",
    )
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "task_runs" in stmt_str:
            # Already running!
            res.scalars.return_value.all.return_value = [mock_running_run]
        else:
            # Return JobConfig
            res.scalar_one_or_none.return_value = mock_job_config
            res.scalars.return_value.all.return_value = [mock_job_config]
        return res
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    mock_job_func = AsyncMock()
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_analysis", mock_job_func)
    ):
        # 2. Act: Execute wrapper
        await run_job_wrapper(job_id=job_id, trigger_type="scheduled")
        
        # 3. Assert: Check that the actual job function was NOT called
        mock_job_func.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_wrapper_saves_timeout_status(monkeypatch):
    # 1. Arrange: Create a mock JobConfig and TaskRun in DB
    job_id = "analysis"
    task_run_id = "test-run-timeout-status"
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    
    mock_job_config = JobConfig(
        id=job_id,
        name="AI Analysis",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=None,
        cooldown_minutes=5,
        volume_threshold=None,
    )
    
    from src.models.schema import TaskRun
    mock_task_run = TaskRun(
        id=task_run_id,
        job_id=job_id,
        task_name="AI Analysis",
        status="timeout", # The task run timed out internally
    )
    
    # Track update calls
    update_values = {}
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "task_runs" in stmt_str:
            if "status =" in stmt_str or ":status_" in stmt_str or "!=" in stmt_str:
                # Check running query (which excludes current task_run_id and checks status)
                res.scalars.return_value.all.return_value = []
            else:
                # Query for specific task run by ID
                res.scalar_one_or_none.return_value = mock_task_run
                res.scalars.return_value.all.return_value = [mock_task_run]
        elif "job_configs" in stmt_str:
            res.scalar_one_or_none.return_value = mock_job_config
            res.scalars.return_value.all.return_value = [mock_job_config]
        
        # Capture update values
        if "update" in stmt_str:
            compiled = stmt.compile()
            update_values.update(compiled.params)
            
        return res
        
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # We mock the job function. It completes without raising exception, but pipeline set TaskRun status to timeout
    mock_job_func = AsyncMock()
    
    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs._job_analysis", mock_job_func)
    ):
        # 2. Act: Execute wrapper
        await run_job_wrapper(job_id=job_id, trigger_type="scheduled", task_run_id=task_run_id)
        
        # 3. Assert: Verify update set last_run_status to "timeout"
        assert any(val == "timeout" for val in update_values.values()), f"last_run_status was not updated to timeout. Update values: {update_values}"


