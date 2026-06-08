import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import traceback

from src.scheduler.jobs import run_job_wrapper
from src.models.schema import TaskRun, JobConfig  # TaskRun does not exist yet!

@pytest.mark.asyncio
async def test_run_job_wrapper_success() -> None:
    # Arrange: Mock the job function, DB session, and session factory
    mock_job_func = AsyncMock()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # We will verify that TaskRun is added to session
    added_objects = []
    def mock_add(obj):
        added_objects.append(obj)
    mock_session.add = mock_add

    # We mock JobConfig retrieval and update query
    mock_job_config = JobConfig(id="dedup", name="Deduplication", enabled=True, trigger_type="interval", schedule_value="60")
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str and "job_configs" in stmt_str:
            result.scalar_one_or_none.return_value = mock_job_config
        return result
    mock_session.execute.side_effect = mock_execute

    with (
        patch("src.scheduler.jobs._job_dedup", mock_job_func),
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory)
    ):
        # Act
        await run_job_wrapper("dedup")

        # Assert
        # Verify job function was called
        mock_job_func.assert_called_once()
        
        # Verify a TaskRun object was created and added to the session
        task_runs = [obj for obj in added_objects if isinstance(obj, TaskRun)]
        assert len(task_runs) == 1
        run_record = task_runs[0]
        assert run_record.job_id == "dedup"
        assert run_record.trigger_type == "scheduled"
        
        # Verify the TaskRun update statement was executed with success status
        update_calls = []
        for call_arg in mock_session.execute.call_args_list:
            stmt = call_arg[0][0]
            stmt_str = str(stmt).lower()
            if "update" in stmt_str and "task_runs" in stmt_str:
                update_calls.append(stmt)
        
        assert len(update_calls) == 1
        params = update_calls[0].compile().params
        status_val = next(v for k, v in params.items() if "status" in k)
        assert status_val == "success"
        
        # Verify session committed
        assert mock_session.commit.call_count >= 1


@pytest.mark.asyncio
async def test_run_job_wrapper_failure() -> None:
    # Arrange: Mock job function to fail
    mock_job_func = AsyncMock(side_effect=ValueError("Simulated LLM rate limit or db error"))
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    added_objects = []
    def mock_add(obj):
        added_objects.append(obj)
    mock_session.add = mock_add

    mock_job_config = JobConfig(id="dedup", name="Deduplication", enabled=True, trigger_type="interval", schedule_value="60")
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str and "job_configs" in stmt_str:
            result.scalar_one_or_none.return_value = mock_job_config
        return result
    mock_session.execute.side_effect = mock_execute

    with (
        patch("src.scheduler.jobs._job_dedup", mock_job_func),
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory)
    ):
        # Act
        await run_job_wrapper("dedup")

        # Assert
        # Verify job function was called
        mock_job_func.assert_called_once()
        
        # Verify TaskRun was added
        task_runs = [obj for obj in added_objects if isinstance(obj, TaskRun)]
        assert len(task_runs) == 1
        run_record = task_runs[0]
        assert run_record.job_id == "dedup"
        
        # Verify the TaskRun update statement was executed with failed status and error message
        update_calls = []
        for call_arg in mock_session.execute.call_args_list:
            stmt = call_arg[0][0]
            stmt_str = str(stmt).lower()
            if "update" in stmt_str and "task_runs" in stmt_str:
                update_calls.append(stmt)
        
        assert len(update_calls) == 1
        params = update_calls[0].compile().params
        status_val = next(v for k, v in params.items() if "status" in k)
        msg_val = next(v for k, v in params.items() if "message" in k)
        
        assert status_val == "failed"
        assert "Simulated LLM" in msg_val
        assert "ValueError" in msg_val
        
        assert mock_session.commit.call_count >= 1


def test_get_tasks_history_endpoint() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.storage.database import get_session

    mock_db_session = MagicMock()
    mock_run = TaskRun(
        id="task-run-uuid",
        job_id="analysis",
        task_name="AI Analysis",
        trigger_type="manual",
        status="success",
        start_time=datetime(2026, 6, 8, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 8, 10, 1, 30, tzinfo=timezone.utc),
        processed_count=18,
        failed_count=2,
        total_count=20,
        message=None
    )

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_run]
        return result
    mock_db_session.execute = AsyncMock(side_effect=mock_execute)

    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)
    response = client.get("/api/tasks/history?job_id=analysis")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "task-run-uuid"
    assert data[0]["job_id"] == "analysis"
    assert data[0]["status"] == "success"
    assert data[0]["processed_count"] == 18
    assert data[0]["failed_count"] == 2
    assert data[0]["total_count"] == 20

    app.dependency_overrides.clear()


def test_active_tasks_and_analysis_stats_endpoints() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.storage.database import get_session

    mock_db_session = MagicMock()
    mock_active_run = TaskRun(
        id="task-run-active-uuid",
        job_id="analysis",
        task_name="AI Analysis",
        trigger_type="manual",
        status="running",
        start_time=datetime(2026, 6, 8, 10, 0, 0, tzinfo=timezone.utc),
        processed_count=5,
        failed_count=1,
        total_count=20,
        message=None
    )

    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "from task_runs" in stmt_str and "status" in stmt_str:
            result.scalars.return_value.all.return_value = [mock_active_run]
            result.scalars.return_value.first.return_value = mock_active_run
        elif "count" in stmt_str and "news_articles" in stmt_str:
            if "analysis_results" in stmt_str or "is_(null)" in stmt_str or "is null" in stmt_str or "is_null" in stmt_str:
                result.scalar_one_or_none.return_value = 15
            else:
                result.scalar_one_or_none.return_value = 100
        else:
            result.scalars.return_value.all.return_value = []
        return result
    mock_db_session.execute = AsyncMock(side_effect=mock_execute)

    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)

    # 1. Test GET /api/tasks/active
    active_resp = client.get("/api/tasks/active")
    assert active_resp.status_code == 200
    active_data = active_resp.json()
    assert len(active_data) == 1
    assert active_data[0]["id"] == "task-run-active-uuid"
    assert active_data[0]["status"] == "running"

    # 2. Test GET /api/tasks/analysis-stats
    stats_resp = client.get("/api/tasks/analysis-stats")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert stats_data["total_news"] == 100
    assert stats_data["pending_news"] == 15
    assert stats_data["active_run"] is not None
    assert stats_data["active_run"]["id"] == "task-run-active-uuid"
    assert stats_data["active_run"]["processed_count"] == 5

    app.dependency_overrides.clear()



