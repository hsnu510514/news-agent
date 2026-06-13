import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from src.api.main import app
from src.core.config import settings
import src.api.routes.system as system_route

@pytest.fixture(autouse=True)
def reset_cache():
    # Reset in-memory cache before every test
    system_route._sources_cache = None
    system_route._sources_cache_time = None

def test_get_newsapi_sources_success():
    # 1. Arrange: Mock settings to have an API key and mock httpx client
    mock_response_data = {
        "status": "ok",
        "sources": [
            {
                "id": "reuters",
                "name": "Reuters",
                "description": "Reuters News Agency",
                "url": "https://www.reuters.com",
                "category": "general",
                "language": "en",
                "country": "us"
            }
        ]
    }
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    # We mock AsyncClient.get to return this mock response
    async def mock_get(*args, **kwargs):
        return mock_resp

    with (
        patch("src.core.config.settings.NEWSAPI_KEY", "dummy_key"),
        patch("httpx.AsyncClient.get", side_effect=mock_get) as mock_http_get
    ):
        client = TestClient(app)
        
        # Act
        response = client.get("/api/system/newsapi-sources")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert len(data["sources"]) == 1
        assert data["sources"][0]["name"] == "Reuters"
        assert data["sources"][0]["url"] == "https://www.reuters.com"
        assert mock_http_get.call_count == 1


def test_get_newsapi_sources_fallback_when_no_key():
    # Arrange: No API key
    with (
        patch("src.core.config.settings.NEWSAPI_KEY", ""),
        patch("httpx.AsyncClient.get") as mock_http_get
    ):
        client = TestClient(app)
        
        # Act
        response = client.get("/api/system/newsapi-sources")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        # Fallback should return a non-empty list of popular sources
        assert len(data["sources"]) > 0
        # Check that Bloomberg or Reuters is in fallback
        source_names = [s["name"] for s in data["sources"]]
        assert "Bloomberg" in source_names
        # Check that httpx client was not called since API key is empty
        mock_http_get.assert_not_called()


def test_get_newsapi_sources_fallback_on_api_error():
    # Arrange: API key is present but httpx call fails
    async def mock_get_fail(*args, **kwargs):
        raise httpx.HTTPStatusError("API Error", request=MagicMock(), response=MagicMock(status_code=500))

    with (
        patch("src.core.config.settings.NEWSAPI_KEY", "dummy_key"),
        patch("httpx.AsyncClient.get", side_effect=mock_get_fail)
    ):
        client = TestClient(app)
        
        # Act
        response = client.get("/api/system/newsapi-sources")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert len(data["sources"]) > 0
        source_names = [s["name"] for s in data["sources"]]
        assert "Reuters" in source_names
