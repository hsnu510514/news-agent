import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import traceback

from src.scheduler.jobs import run_job_wrapper
from src.models.schema import TaskRun, JobConfig, NewsArticle

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

    mock_job_config = JobConfig(id="preprocessing", name="News Pre-processing", enabled=True, trigger_type="interval", schedule_value="30")
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str and "job_configs" in stmt_str:
            result.scalar_one_or_none.return_value = mock_job_config
        return result
    mock_session.execute.side_effect = mock_execute

    with (
        patch("src.scheduler.jobs._job_preprocessing", mock_job_func),
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory)
    ):
        # Act
        await run_job_wrapper("preprocessing")

        # Assert
        # Verify job function was called
        mock_job_func.assert_called_once()
        
        # Verify a TaskRun object was created and added to the session
        task_runs = [obj for obj in added_objects if isinstance(obj, TaskRun)]
        assert len(task_runs) == 1
        run_record = task_runs[0]
        assert run_record.job_id == "preprocessing"
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

    mock_job_config = JobConfig(id="preprocessing", name="News Pre-processing", enabled=True, trigger_type="interval", schedule_value="30")
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str and "job_configs" in stmt_str:
            result.scalar_one_or_none.return_value = mock_job_config
        return result
    mock_session.execute.side_effect = mock_execute

    with (
        patch("src.scheduler.jobs._job_preprocessing", mock_job_func),
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory)
    ):
        # Act
        await run_job_wrapper("preprocessing")

        # Assert
        # Verify job function was called
        mock_job_func.assert_called_once()
        
        # Verify TaskRun was added
        task_runs = [obj for obj in added_objects if isinstance(obj, TaskRun)]
        assert len(task_runs) == 1
        run_record = task_runs[0]
        assert run_record.job_id == "preprocessing"
        
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
        stmt_str = str(stmt).lower()
        if "count(" in stmt_str:
            result.scalar_one = MagicMock(return_value=1)
        else:
            result.scalars.return_value.all.return_value = [mock_run]
        return result
    mock_db_session.execute = AsyncMock(side_effect=mock_execute)

    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)
    response = client.get("/api/tasks/history?job_id=analysis&limit=20&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["offset"] == 0
    assert data["limit"] == 20
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "task-run-uuid"
    assert data["items"][0]["job_id"] == "analysis"
    assert data["items"][0]["status"] == "success"
    assert data["items"][0]["processed_count"] == 18
    assert data["items"][0]["failed_count"] == 2
    assert data["items"][0]["total_count"] == 20

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


@pytest.mark.asyncio
async def test_setup_jobs_deletes_outdated_jobs() -> None:
    # Arrange
    from src.scheduler.jobs import setup_jobs, DEFAULT_JOBS
    
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.delete = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # Database returns a deprecated job config along with a valid one
    valid_job = JobConfig(id=DEFAULT_JOBS[0]["id"], name=DEFAULT_JOBS[0]["name"], enabled=True, trigger_type="interval", schedule_value="15")
    deprecated_job = JobConfig(id="jin10", name="jin10 Flash News", enabled=True, trigger_type="interval", schedule_value="15")
    
    # We will track which job configs are deleted
    deleted_jobs = []
    def mock_delete(obj):
        deleted_jobs.append(obj)
    mock_session.delete.side_effect = mock_delete

    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str and "job_configs" in stmt_str:
            result.scalars.return_value.all.return_value = [valid_job, deprecated_job]
        return result
    mock_session.execute.side_effect = mock_execute

    with (
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory),
        patch("src.scheduler.jobs.scheduler") as mock_scheduler,
    ):
        # Act
        await setup_jobs()

        # Assert
        # Verify that the deprecated job config 'jin10' was deleted from session
        assert len(deleted_jobs) == 1
        assert deleted_jobs[0].id == "jin10"
        assert mock_session.commit.call_count >= 1


def test_stop_task_run_endpoint() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.storage.database import get_session

    mock_db_session = MagicMock()
    mock_run = TaskRun(
        id="task-run-uuid-1",
        job_id="preprocessing",
        task_name="News Pre-processing",
        trigger_type="manual",
        status="running",
        start_time=datetime(2026, 6, 8, 10, 0, 0, tzinfo=timezone.utc),
    )

    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str:
            result.scalar_one_or_none.return_value = mock_run
        return result

    mock_db_session.execute = AsyncMock(side_effect=mock_execute)
    mock_db_session.commit = AsyncMock()

    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)
    response = client.post("/api/tasks/task-run-uuid-1/stop")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stopped"
    assert data["task_run_id"] == "task-run-uuid-1"

    # Verify TaskRun status is updated
    assert mock_run.status == "failed"
    assert mock_run.message == "Stopped by user"
    assert mock_run.end_time is not None
    assert mock_db_session.commit.call_count >= 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preprocessing_loop_cancellation() -> None:
    # Test that pre-processing loop exits early if TaskRun status changes to failed/stopped
    from src.ingest.preprocessing import run_preprocessing_pipeline
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    art1 = NewsArticle(id="art-1", title="A1", content="C1", is_relevant=None)
    art2 = NewsArticle(id="art-2", title="A2", content="C2", is_relevant=None)

    # First query fetches the two articles.
    # Second query inside loop checks TaskRun status - return "failed" (indicating it was stopped)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [art1, art2]

    async def mock_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt).lower()
        result = MagicMock()
        if "is_relevant is null" in stmt_str or "is_relevant is_(null)" in stmt_str or "is null" in stmt_str:
            result.scalars.return_value = mock_scalars
        elif "status" in stmt_str and "task_runs" in stmt_str:
            # TaskRun status is queried inside the loop - return "failed" (stopped)
            result.scalar.return_value = "failed"
        else:
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.first.return_value = None
        return result

    mock_session.execute.side_effect = mock_execute

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.ingest.preprocessing.async_session_factory", mock_session_factory),
        patch("src.ingest.preprocessing.check_relevance", new_callable=AsyncMock) as mock_check,
    ):
        # Act
        stats = await run_preprocessing_pipeline(task_run_id="test-task-run")

        # Assert
        # The loop should break immediately before processing art1 because the status is "failed"
        assert stats["processed"] == 0
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_loop_cancellation() -> None:
    # Test that AI analysis loop exits early if TaskRun status changes to failed/stopped
    from src.analysis.classifier import run_analysis_pipeline

    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    art1 = NewsArticle(id="art-1", title="A1", content="C1", is_relevant=True, published_at=datetime.now(timezone.utc))
    art2 = NewsArticle(id="art-2", title="A2", content="C2", is_relevant=True, published_at=datetime.now(timezone.utc))

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [art1, art2]

    async def mock_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt).lower()
        result = MagicMock()
        if "analysis_results" in stmt_str and "select" in stmt_str:
            result.scalars.return_value = mock_scalars
        elif "status" in stmt_str and "task_runs" in stmt_str:
            result.scalar.return_value = "failed"
        else:
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.first.return_value = None
        return result

    mock_session.execute.side_effect = mock_execute

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.analysis.classifier.async_session_factory", mock_session_factory),
        patch("src.analysis.classifier.process_article_sequentially", new_callable=AsyncMock) as mock_process,
    ):
        # Act
        stats = await run_analysis_pipeline(task_run_id="test-task-run")

        # Assert
        assert stats["analyzed"] == 0
        mock_process.assert_not_called()





