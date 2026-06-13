import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from src.api.main import app
from src.storage.database import get_session
from src.models.schema import JobConfig

@pytest.fixture
def client_and_session():
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = MagicMock()
    mock_session.commit = AsyncMock()
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, mock_session
    app.dependency_overrides.clear()

def test_get_jobs_returns_cooldown_calculation(client_and_session) -> None:
    client, mock_session = client_and_session
    
    # 1. Arrange: Create mock JobConfigs
    # Job 1: In cooldown (run 2 mins ago, cooldown is 5 mins)
    job_in_cooldown = JobConfig(
        id="preprocessing",
        name="News Pre-processing",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=datetime.now(timezone.utc) - timedelta(minutes=2),
        cooldown_minutes=5,
        volume_threshold=None,
    )
    # Job 2: Not in cooldown (run 10 mins ago, cooldown is 5 mins)
    job_not_in_cooldown = JobConfig(
        id="analysis",
        name="AI Analysis",
        enabled=True,
        trigger_type="interval",
        schedule_value="10",
        last_run_time=datetime.now(timezone.utc) - timedelta(minutes=10),
        cooldown_minutes=5,
        volume_threshold=None,
    )
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [job_in_cooldown, job_not_in_cooldown]
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    
    # Mock apscheduler job next run
    mock_apsched_job = MagicMock()
    mock_apsched_job.next_run_time = datetime.now(timezone.utc)
    
    with patch("src.api.routes.scheduler.scheduler.get_job", return_value=mock_apsched_job):
        # 2. Act: Call GET /api/scheduler/jobs
        response = client.get("/api/scheduler/jobs")
        assert response.status_code == 200
        data = response.json()
        
        # 3. Assert: Verify returned schema has in_cooldown and cooldown_remaining_seconds
        assert len(data) == 2
        
        preprocessing = next(j for j in data if j["id"] == "preprocessing")
        assert preprocessing["in_cooldown"] is True
        assert 170 <= preprocessing["cooldown_remaining_seconds"] <= 180
        
        analysis = next(j for j in data if j["id"] == "analysis")
        assert analysis["in_cooldown"] is False
        assert analysis["cooldown_remaining_seconds"] == 0
