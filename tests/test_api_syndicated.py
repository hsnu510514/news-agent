import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.api.main import app
from src.storage.database import get_session
from src.models.schema import NewsArticle, LanguageEnum, SourceTypeEnum

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

def test_list_news_excludes_syndicated(client_and_session) -> None:
    client, mock_session = client_and_session
    
    # Create article
    article = NewsArticle(
        id="canonical-art-1",
        title="Primary Source Article",
        url="https://test.com/1",
        source_type=SourceTypeEnum.RSS,
        source_name="Reuters",
        language=LanguageEnum.EN,
        published_at=datetime.now(),
        fetched_at=datetime.now(),
    )
    
    mock_execute_result = MagicMock()
    # Mock total count scalar
    mock_execute_result.scalar_one.return_value = 1
    # Mock results scalars
    mock_execute_result.scalars.return_value.all.return_value = [article]
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/news")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "canonical-art-1"
    
    # Check that query statement has is_(None) check on duplicate_of_id
    # Get the statement passed to execute
    called_stmt = mock_session.execute.call_args[0][0]
    called_stmt_str = str(called_stmt).lower()
    assert "duplicate_of_id is null" in called_stmt_str

def test_list_syndicated_news(client_and_session) -> None:
    client, mock_session = client_and_session
    
    primary = NewsArticle(
        id="canonical-art-2",
        title="Primary Source Article",
        url="https://test.com/2",
        source_type=SourceTypeEnum.RSS,
        source_name="Reuters",
    )
    syndicated = NewsArticle(
        id="syndicated-art-2",
        title="Syndicated Copy",
        url="https://test.com/2-dup",
        source_type=SourceTypeEnum.RSS,
        source_name="Bloomberg",
        language=LanguageEnum.EN,
        published_at=datetime.now(),
        fetched_at=datetime.now(),
        duplicate_of_id="canonical-art-2",
    )
    syndicated.duplicate_of = primary
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one.return_value = 1
    mock_execute_result.scalars.return_value.all.return_value = [syndicated]
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/news/syndicated")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == "syndicated-art-2"
    assert item["primary_source"]["id"] == "canonical-art-2"
    assert item["primary_source"]["title"] == "Primary Source Article"
