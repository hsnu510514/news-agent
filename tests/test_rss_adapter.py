import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.news_fetcher import RssIngestAdapter
from src.models.schema import NewsArticle, LanguageEnum, SourceTypeEnum


@pytest.mark.asyncio
async def test_rss_adapter_fetch_and_parse() -> None:
    # 1. Arrange
    mock_session = MagicMock(spec=AsyncSession)
    
    mock_rss_feeds = {
        "en": [{"name": "Reuters EN", "url": "https://reuters.com/rss", "category": "General"}]
    }

    mock_response = MagicMock()
    mock_response.text = "<rss><channel><title>Reuters</title></channel></rss>"
    mock_response.raise_for_status = MagicMock()
    
    class MockEntry(dict):
        def __getattr__(self, name):
            return self.get(name)
            
    mock_entry = MockEntry({
        "link": "https://reuters.com/article-reuters-1",
        "title": "US Inflation Drops",
        "summary": "Inflation has dropped significantly this quarter.",
        "published_parsed": (2026, 6, 6, 12, 0, 0, 5, 157, 0),
    })
    
    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]
    
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    adapter = RssIngestAdapter()
    
    with (
        patch("src.ingest.news_fetcher.get_rss_feeds", return_value=mock_rss_feeds),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("feedparser.parse", return_value=mock_feed),
    ):
        mock_settings.ENABLED_RSS_FEEDS = "Reuters EN"
        mock_settings.DELETED_RSS_FEEDS = ""
        mock_settings.CUSTOM_RSS_FEEDS = "[]"
        
        # 2. Act
        articles = await adapter.fetch(mock_client, mock_session)
        
        # 3. Assert
        assert len(articles) == 1
        art = articles[0]
        assert isinstance(art, NewsArticle)
        assert art.title == "US Inflation Drops"
        assert art.url == "https://reuters.com/article-reuters-1"
        assert art.source_name == "Reuters EN"
        assert art.language == LanguageEnum.EN
        assert art.source_type == SourceTypeEnum.RSS
        assert art.content == "Inflation has dropped significantly this quarter."
        assert art.published_at == datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc)
        assert art.is_relevant is None  # Defaults to pending pre-processing


@pytest.mark.asyncio
async def test_rss_adapter_filter_duplicates() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [("existing_hash_1",)]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    adapter = RssIngestAdapter()
    
    articles = [
        NewsArticle(url="https://a.com", url_hash="existing_hash_1", title="A"),
        NewsArticle(url="https://b.com", url_hash="new_hash_2", title="B"),
        # Duplicate url_hash within the list itself
        NewsArticle(url="https://c.com", url_hash="new_hash_2", title="C"),
    ]
    
    # Act
    filtered = await adapter.filter_duplicates(articles, mock_session)
    
    # Assert
    assert len(filtered) == 1
    assert filtered[0].url_hash == "new_hash_2"
    mock_session.execute.assert_called_once()

