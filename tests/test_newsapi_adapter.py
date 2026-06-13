import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.newsapi_fetcher import NewsApiIngestAdapter
from src.models.schema import NewsArticle, LanguageEnum, SourceTypeEnum


@pytest.mark.asyncio
async def test_newsapi_adapter_fetch_and_parse() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "ok",
        "articles": [
            {
                "url": "https://bloomberg.com/news-1",
                "title": "Fed Hikes Rates",
                "description": "The Federal Reserve raised interest rates.",
                "content": "Full content of the article...",
                "publishedAt": "2026-06-13T12:00:00Z",
                "author": "John Doe",
                "urlToImage": "https://bloomberg.com/img.png",
                "source": {"name": "Bloomberg"}
            }
        ]
    }
    
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    adapter = NewsApiIngestAdapter()
    
    with (
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        mock_settings.NEWSAPI_DOMAINS = ""
        
        # Act
        articles = await adapter.fetch(mock_client, mock_session)
        
        # Assert
        # There should be articles for both en and zh since we mock the same response for both calls
        assert len(articles) == 2
        art = articles[0]
        assert isinstance(art, NewsArticle)
        assert art.title == "Fed Hikes Rates"
        assert art.url == "https://bloomberg.com/news-1"
        assert art.source_name == "Bloomberg"
        assert art.language == LanguageEnum.EN  # First query is "en"
        assert art.source_type == SourceTypeEnum.NEWSAPI
        assert art.content == "Full content of the article..."
        assert art.summary == "The Federal Reserve raised interest rates."
        assert art.published_at == datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)
        assert art.is_relevant is None


@pytest.mark.asyncio
async def test_newsapi_adapter_filter_duplicates() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [("existing_hash_1",)]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    adapter = NewsApiIngestAdapter()
    
    articles = [
        NewsArticle(url="https://a.com", url_hash="existing_hash_1", title="A"),
        NewsArticle(url="https://b.com", url_hash="new_hash_2", title="B"),
        # Duplicate within the list itself
        NewsArticle(url="https://c.com", url_hash="new_hash_2", title="C"),
    ]
    
    # Act
    filtered = await adapter.filter_duplicates(articles, mock_session)
    
    # Assert
    assert len(filtered) == 1
    assert filtered[0].url_hash == "new_hash_2"
    mock_session.execute.assert_called_once()
