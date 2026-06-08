import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingest.news_fetcher import ingest_rss
from src.ingest.newsapi_fetcher import ingest_newsapi
from src.models.schema import NewsArticle, LanguageEnum

@pytest.mark.asyncio
async def test_ingest_rss_irrelevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_rss_feeds = {
        "en": [{"name": "Test English Feed", "url": "https://test.com/rss", "category": "General"}]
    }

    mock_response = MagicMock()
    mock_response.text = "<rss>...</rss>"
    mock_response.raise_for_status = MagicMock()
    
    class MockEntry(dict):
        def __getattr__(self, name):
            return self.get(name)
            
    mock_entry = MockEntry({
        "link": "https://test.com/article1",
        "title": "Irrelevant Political News",
        "summary": "Some general political debate summary.",
        "published_parsed": (2026, 6, 6, 12, 0, 0, 5, 157, 0),
    })
    
    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]

    with (
        patch("src.ingest.news_fetcher.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.RSS_FEEDS", mock_rss_feeds),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock) as mock_check,
    ):
        mock_check.return_value = False
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        assert saved_count == 0
        
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert isinstance(article, NewsArticle)
        assert article.title == "Irrelevant Political News"
        assert article.is_relevant is False
        assert article.content is None
        assert article.content_hash is None
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_rss_relevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_rss_feeds = {
        "en": [{"name": "Test English Feed", "url": "https://test.com/rss", "category": "General"}]
    }

    mock_response = MagicMock()
    mock_response.text = "<rss>...</rss>"
    mock_response.raise_for_status = MagicMock()
    
    class MockEntry(dict):
        def __getattr__(self, name):
            return self.get(name)
            
    mock_entry = MockEntry({
        "link": "https://test.com/article2",
        "title": "Nvidia Blackwell GPU Delayed",
        "summary": "Nvidia is facing GPU delays.",
        "published_parsed": (2026, 6, 6, 12, 0, 0, 5, 157, 0),
    })
    
    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]

    with (
        patch("src.ingest.news_fetcher.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.RSS_FEEDS", mock_rss_feeds),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock) as mock_check,
    ):
        mock_check.return_value = True
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        assert saved_count == 1
        
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert isinstance(article, NewsArticle)
        assert article.title == "Nvidia Blackwell GPU Delayed"
        assert article.is_relevant is True
        assert article.content == "Nvidia is facing GPU delays."
        assert article.content_hash is not None
        mock_check.assert_called_once_with("Nvidia Blackwell GPU Delayed", "Nvidia is facing GPU delays.")
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_newsapi_irrelevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "status": "ok",
        "articles": [
            {
                "url": "https://newsapi.com/article_irrelevant",
                "title": "Irrelevant Political Debates",
                "description": "General discussions about election polls.",
                "content": "Full content preview here...",
                "publishedAt": "2026-06-06T12:00:00Z",
                "source": {"name": "CNN"}
            }
        ]
    })
    
    with (
        patch("src.ingest.newsapi_fetcher.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock) as mock_check,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        mock_check.return_value = False
        
        # Act
        saved_count = await ingest_newsapi()
        
        # Assert
        assert saved_count == 0
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 2
        for article in added_objs:
            assert isinstance(article, NewsArticle)
            assert article.title == "Irrelevant Political Debates"
            assert article.is_relevant is False
            assert article.content is None
            assert article.content_hash is None
        mock_check.assert_any_call("Irrelevant Political Debates", "General discussions about election polls.")
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_ingest_newsapi_relevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "status": "ok",
        "articles": [
            {
                "url": "https://newsapi.com/article_relevant",
                "title": "Fed Hikes Interest Rates",
                "description": "The Federal Reserve raised interest rates by 25 basis points.",
                "content": "Full content preview here...",
                "publishedAt": "2026-06-06T12:00:00Z",
                "source": {"name": "Bloomberg"}
            }
        ]
    })
    
    with (
        patch("src.ingest.newsapi_fetcher.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock) as mock_check,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        mock_check.return_value = True
        
        # Act
        saved_count = await ingest_newsapi()
        
        # Assert
        assert saved_count == 2
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 2
        for article in added_objs:
            assert isinstance(article, NewsArticle)
            assert article.title == "Fed Hikes Interest Rates"
            assert article.is_relevant is True
            assert article.content == "Full content preview here..."
            assert article.content_hash is not None
            assert article.summary == "The Federal Reserve raised interest rates by 25 basis points."
        mock_check.assert_any_call("Fed Hikes Interest Rates", "The Federal Reserve raised interest rates by 25 basis points.")
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_ingest_skips_existing_url_hash() -> None:
    # Arrange
    existing_article = NewsArticle(
        url="https://test.com/article-already-exists",
        url_hash="some_hash",
        title="Existing Article",
        is_relevant=True,
    )
    
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=existing_article)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # For RSS
    mock_rss_feeds = {
        "en": [{"name": "Test English Feed", "url": "https://test.com/rss", "category": "General"}]
    }
    mock_response_rss = MagicMock()
    mock_response_rss.text = "<rss>...</rss>"
    mock_response_rss.raise_for_status = MagicMock()
    
    class MockEntry(dict):
        def __getattr__(self, name):
            return self.get(name)
            
    mock_entry_rss = MockEntry({
        "link": "https://test.com/article-already-exists",
        "title": "Existing Article",
        "summary": "Summary",
    })
    mock_feed_rss = MagicMock()
    mock_feed_rss.entries = [mock_entry_rss]

    # For NewsAPI
    mock_response_newsapi = MagicMock()
    mock_response_newsapi.json = MagicMock(return_value={
        "status": "ok",
        "articles": [
            {
                "url": "https://test.com/article-already-exists",
                "title": "Existing Article",
                "description": "Description",
                "content": "Content",
                "publishedAt": "2026-06-06T12:00:00Z",
                "source": {"name": "Test"}
            }
        ]
    })

    # Test RSS skipping
    with (
        patch("src.ingest.news_fetcher.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.RSS_FEEDS", mock_rss_feeds),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response_rss),
        patch("feedparser.parse", return_value=mock_feed_rss),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock) as mock_check_rss,
    ):
        saved_count = await ingest_rss()
        assert saved_count == 0
        mock_check_rss.assert_not_called()
        mock_session.add.assert_not_called()

    # Reset mock_session.add for NewsAPI test
    mock_session.add.reset_mock()

    # Test NewsAPI skipping
    with (
        patch("src.ingest.newsapi_fetcher.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response_newsapi),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock) as mock_check_newsapi,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        saved_count = await ingest_newsapi()
        assert saved_count == 0
        mock_check_newsapi.assert_not_called()
        mock_session.add.assert_not_called()

