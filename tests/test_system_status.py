import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.main import app
from src.storage.database import get_session

def test_system_status_endpoint_healthy():
    # 1. Arrange: Mock DB (success) and Qdrant (success)
    mock_db_session = MagicMock()
    mock_db_session.execute = AsyncMock()  # SELECT 1 succeeds
    
    async def override_get_session():
        yield mock_db_session
        
    app.dependency_overrides[get_session] = override_get_session
    
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.get_collection = MagicMock() # Succeeds
    
    mock_tracker = MagicMock()
    mock_tracker.status = "healthy"
    mock_tracker.error_message = ""
    mock_tracker.requests_made_today = 45
    mock_tracker.estimated_daily_limit = 1500

    with (
        patch("src.api.main.client", mock_qdrant_client),
        patch("src.api.main.api_status_tracker", mock_tracker)
    ):
        # 2. Act: Call endpoint
        client = TestClient(app)
        response = client.get("/api/system/status")
            
        # 3. Assert: Verify healthy response
        assert response.status_code == 200
        data = response.json()
        assert data["llm_api"] == {
            "status": "healthy",
            "error_message": "",
            "requests_made_today": 45,
            "estimated_daily_limit": 1500
        }
        assert data["database"] == {
            "status": "healthy",
            "error_message": ""
        }
        assert data["qdrant"] == {
            "status": "healthy",
            "error_message": ""
        }
    
    app.dependency_overrides.clear()


def test_system_status_endpoint_failures():
    # 1. Arrange: Mock DB (failure), Qdrant (failure), and LLM API (rate limited)
    mock_db_session = MagicMock()
    mock_db_session.execute = AsyncMock(side_effect=Exception("Database connection timed out"))
    
    async def override_get_session():
        yield mock_db_session
        
    app.dependency_overrides[get_session] = override_get_session
    
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.get_collection = MagicMock(side_effect=Exception("Qdrant not reachable"))
    
    mock_tracker = MagicMock()
    mock_tracker.status = "rate_limited"
    mock_tracker.error_message = "Quota limit reached"
    mock_tracker.requests_made_today = 1500
    mock_tracker.estimated_daily_limit = 1500

    with (
        patch("src.api.main.client", mock_qdrant_client),
        patch("src.api.main.api_status_tracker", mock_tracker)
    ):
        # 2. Act: Call endpoint
        client = TestClient(app)
        response = client.get("/api/system/status")
            
        # 3. Assert: Verify failure outputs are captured
        assert response.status_code == 200
        data = response.json()
        assert data["llm_api"]["status"] == "rate_limited"
        assert data["llm_api"]["error_message"] == "Quota limit reached"
        assert data["database"]["status"] == "error"
        assert "Database connection timed out" in data["database"]["error_message"]
        assert data["qdrant"]["status"] == "error"
        assert "Qdrant not reachable" in data["qdrant"]["error_message"]
        
    app.dependency_overrides.clear()
