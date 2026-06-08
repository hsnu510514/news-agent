import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.api.main import app
from src.storage.database import get_session
from src.models.schema import MarketWire, SourceTypeEnum, LanguageEnum

@pytest.fixture
def client_and_session():
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, mock_session
    app.dependency_overrides.clear()

def test_api_market_wire_endpoint(client_and_session) -> None:
    client, mock_session = client_and_session
    
    wire = MarketWire(
        id="wire-123",
        content="Breaking: Federal Reserve hints at rate cut.",
        content_hash="hash-123",
        source_type=SourceTypeEnum.JIN10,
        language=LanguageEnum.EN,
        importance=1,
        related_symbols=["US-FED"],
        published_at=datetime.now(),
    )
    
    mock_execute_result = MagicMock()
    # Mock total count scalar
    mock_execute_result.scalar_one.return_value = 1
    # Mock results scalars
    mock_execute_result.scalars.return_value.all.return_value = [wire]
    
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/market-wire")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] == 1
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "wire-123"
    assert data["items"][0]["content"] == "Breaking: Federal Reserve hints at rate cut."
