import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingest.news_fetcher import ingest_rss
from src.ingest.newsapi_fetcher import ingest_newsapi
from src.models.schema import NewsArticle, LanguageEnum

@pytest.mark.asyncio
async def test_ingest_rss_irrelevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
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
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.get_rss_feeds", return_value=mock_rss_feeds),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.ENABLED_RSS_FEEDS = "Test English Feed"
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        assert saved_count == 1
        
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert isinstance(article, NewsArticle)
        assert article.title == "Irrelevant Political News"
        assert article.is_relevant is None
        assert article.content == "Some general political debate summary."
        assert article.content_hash is None
        mock_check.assert_not_called()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_rss_relevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
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
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.get_rss_feeds", return_value=mock_rss_feeds),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.ENABLED_RSS_FEEDS = "Test English Feed"
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        assert saved_count == 1
        
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert isinstance(article, NewsArticle)
        assert article.title == "Nvidia Blackwell GPU Delayed"
        assert article.is_relevant is None
        assert article.content == "Nvidia is facing GPU delays."
        assert article.content_hash is None
        mock_check.assert_not_called()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_newsapi_irrelevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(side_effect=[
        {
            "status": "ok",
            "articles": [
                {
                    "url": "https://newsapi.com/article_irrelevant_1",
                    "title": "Irrelevant Political Debates",
                    "description": "General discussions about election polls.",
                    "content": "Full content preview here...",
                    "publishedAt": "2026-06-06T12:00:00Z",
                    "source": {"name": "CNN"}
                }
            ]
        },
        {
            "status": "ok",
            "articles": [
                {
                    "url": "https://newsapi.com/article_irrelevant_2",
                    "title": "Irrelevant Political Debates",
                    "description": "General discussions about election polls.",
                    "content": "Full content preview here...",
                    "publishedAt": "2026-06-06T12:00:00Z",
                    "source": {"name": "CNN"}
                }
            ]
        }
    ])
    
    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        
        # Act
        saved_count = await ingest_newsapi()
        
        # Assert
        assert saved_count == 2
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 2
        for article in added_objs:
            assert isinstance(article, NewsArticle)
            assert article.title == "Irrelevant Political Debates"
            assert article.is_relevant is None
            assert article.content == "Full content preview here..."
            assert article.content_hash is None
        mock_check.assert_not_called()
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_ingest_newsapi_relevant() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(side_effect=[
        {
            "status": "ok",
            "articles": [
                {
                    "url": "https://newsapi.com/article_relevant_1",
                    "title": "Fed Hikes Interest Rates",
                    "description": "The Federal Reserve raised interest rates by 25 basis points.",
                    "content": "Full content preview here...",
                    "publishedAt": "2026-06-06T12:00:00Z",
                    "source": {"name": "Bloomberg"}
                }
            ]
        },
        {
            "status": "ok",
            "articles": [
                {
                    "url": "https://newsapi.com/article_relevant_2",
                    "title": "Fed Hikes Interest Rates",
                    "description": "The Federal Reserve raised interest rates by 25 basis points.",
                    "content": "Full content preview here...",
                    "publishedAt": "2026-06-06T12:00:00Z",
                    "source": {"name": "Bloomberg"}
                }
            ]
        }
    ])
    
    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        
        # Act
        saved_count = await ingest_newsapi()
        
        # Assert
        assert saved_count == 2
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 2
        for article in added_objs:
            assert isinstance(article, NewsArticle)
            assert article.title == "Fed Hikes Interest Rates"
            assert article.is_relevant is None
            assert article.content == "Full content preview here..."
            assert article.content_hash is None
            assert article.summary == "The Federal Reserve raised interest rates by 25 basis points."
        mock_check.assert_not_called()
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
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=existing_article)
    mock_session.execute.return_value.all.return_value = [("3700a410574bbe2d8cfbf8f2d200146506ed78a66850f41d73e171e89e9e5e1a",)]
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
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.get_rss_feeds", return_value=mock_rss_feeds),
        patch("src.ingest.news_fetcher.settings") as mock_settings_rss,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response_rss),
        patch("feedparser.parse", return_value=mock_feed_rss),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check_rss,
    ):
        mock_settings_rss.ENABLED_RSS_FEEDS = "Test English Feed"
        saved_count = await ingest_rss()
        assert saved_count == 0
        mock_check_rss.assert_not_called()
        mock_session.add.assert_not_called()

    # Reset mock_session.add for NewsAPI test
    mock_session.add.reset_mock()

    # Test NewsAPI skipping
    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response_newsapi),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check_newsapi,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        saved_count = await ingest_newsapi()
        assert saved_count == 0
        mock_check_newsapi.assert_not_called()
        mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_rss_filtering_by_enabled_feeds() -> None:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_rss_feeds = {
        "en": [
            {"name": "EnabledFeed", "url": "https://test.com/enabled_rss", "category": "General"},
            {"name": "DisabledFeed", "url": "https://test.com/disabled_rss", "category": "General"}
        ]
    }

    mock_response = MagicMock()
    mock_response.text = "<rss>...</rss>"
    mock_response.raise_for_status = MagicMock()
    
    class MockEntry(dict):
        def __getattr__(self, name):
            return self.get(name)
            
    mock_entry = MockEntry({
        "link": "https://test.com/article1",
        "title": "Article Title",
        "summary": "Summary text",
        "published_parsed": (2026, 6, 6, 12, 0, 0, 5, 157, 0),
    })
    
    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.get_rss_feeds", return_value=mock_rss_feeds),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.ENABLED_RSS_FEEDS = "EnabledFeed"
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        # Should only fetch for EnabledFeed (1 article), DisabledFeed should be skipped completely
        assert saved_count == 1
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_newsapi_filtering_by_domains() -> None:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={"status": "ok", "articles": []})
    
    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_http_get,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        mock_settings.NEWSAPI_DOMAINS = "bloomberg.com,reuters.com"
        
        # Act
        await ingest_newsapi()
        
        # Assert
        # The GET call should pass the domains query parameter
        called_args, called_kwargs = mock_http_get.call_args
        params = called_kwargs.get("params") or called_args[1]
        assert params["domains"] == "bloomberg.com,reuters.com"


@pytest.mark.asyncio
async def test_ingest_akshare_cpi_ppi_parsing() -> None:
    import pandas as pd
    
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # DataFrame mock for CPI
    cpi_df = pd.DataFrame([
        {"商品": "CPI", "日期": "2026-04-01", "今值": "0.1", "预测值": "0.2", "前值": "0.0"},
        {"商品": "CPI", "日期": "2026-05-01", "今值": "0.3", "预测值": "0.2", "前值": "0.1"}
    ])
    
    # DataFrame mock for GDP (which uses default columns 0/1)
    gdp_df = pd.DataFrame([
        {"日期": "2026-04-01", "今值": "5.0"},
        {"日期": "2026-05-01", "今值": "5.2"}
    ])

    mock_akshare = MagicMock()
    mock_akshare.macro_china_cpi_yearly.return_value = cpi_df
    mock_akshare.macro_china_gdp.return_value = gdp_df
    mock_akshare.macro_china_ppi_yearly.return_value = cpi_df
    mock_akshare.macro_china_pmi.return_value = gdp_df
    mock_akshare.macro_china_money_supply.return_value = gdp_df
    mock_akshare.macro_china_lpr.return_value = gdp_df

    # We patch sys.modules to mock 'akshare' import
    import sys
    sys.modules["akshare"] = mock_akshare

    from src.ingest.macro_fetcher import ingest_akshare

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
    ):
        # Act
        saved_count = await ingest_akshare()
        
        # Assert
        assert saved_count > 0
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        
        cpi_entries = [obj for obj in added_objs if obj.indicator_code == "CPI_CN"]
        assert len(cpi_entries) == 1
        cpi_entry = cpi_entries[0]
        assert cpi_entry.value == 0.3
        assert cpi_entry.period == "2026-05"
        assert cpi_entry.previous_value == 0.1

        # Clean up sys.modules
        del sys.modules["akshare"]


@pytest.mark.asyncio
async def test_ingest_fred_pmi() -> None:
    import pandas as pd
    
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # DataFrame mock for FRED series
    pmi_series = pd.Series([50.1, 51.3], index=[pd.Timestamp("2026-04-01"), pd.Timestamp("2026-05-01")])
    
    mock_fred = MagicMock()
    mock_fred.get_series_latest_release.return_value = pmi_series

    # We patch sys.modules to mock 'fredapi' import
    import sys
    mock_fredapi = MagicMock()
    mock_fredapi.Fred.return_value = mock_fred
    sys.modules["fredapi"] = mock_fredapi

    from src.ingest.macro_fetcher import ingest_fred

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.macro_fetcher.settings") as mock_settings,
    ):
        mock_settings.FRED_API_KEY = "test_fred_key"
        
        # Act
        saved_count = await ingest_fred()
        
        # Assert
        assert saved_count > 0
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        
        pmi_entries = [obj for obj in added_objs if obj.indicator_code == "PMI"]
        assert len(pmi_entries) == 1
        pmi_entry = pmi_entries[0]
        assert pmi_entry.value == 51.3
        assert pmi_entry.period == "2026-05"
        assert pmi_entry.previous_value == 50.1

        # Clean up sys.modules
        del sys.modules["fredapi"]


@pytest.mark.asyncio
async def test_ingest_rss_custom_feed() -> None:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.text = "<rss>...</rss>"
    mock_response.raise_for_status = MagicMock()
    
    class MockEntry(dict):
        def __getattr__(self, name):
            return self.get(name)
            
    mock_entry = MockEntry({
        "link": "https://customfeed.com/article1",
        "title": "Custom Feed Nvidia Blackwell Delay",
        "summary": "Delay details",
        "published_parsed": (2026, 6, 6, 12, 0, 0, 5, 157, 0),
    })
    
    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_http_get,
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        # Configure settings to have a custom feed
        mock_settings.CUSTOM_RSS_FEEDS = '[{"name": "CustomFeed", "url": "https://customfeed.com/rss", "category": "finance", "language": "en"}]'
        mock_settings.ENABLED_RSS_FEEDS = "CustomFeed"
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        assert saved_count == 1
        mock_http_get.assert_called_once_with("https://customfeed.com/rss")
        
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert article.title == "Custom Feed Nvidia Blackwell Delay"
        assert article.source_name == "CustomFeed"
        assert article.language == LanguageEnum.EN
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_rss_deleted_predefined_feed() -> None:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_http_get,
    ):
        # Configure settings: 36Kr is enabled, but also deleted.
        mock_settings.ENABLED_RSS_FEEDS = "36Kr"
        mock_settings.CUSTOM_RSS_FEEDS = "[]"
        mock_settings.DELETED_RSS_FEEDS = "36Kr"
        
        # Act
        saved_count = await ingest_rss()
        
        # Assert
        assert saved_count == 0
        mock_http_get.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_rss_updates_task_run() -> None:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute.return_value.scalar.return_value = "running"
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

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
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.news_fetcher.get_rss_feeds", return_value=mock_rss_feeds),
        patch("src.ingest.news_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("feedparser.parse", return_value=mock_feed),
        patch("src.ingest.news_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.ENABLED_RSS_FEEDS = "Test English Feed"
        mock_settings.DELETED_RSS_FEEDS = ""
        mock_settings.CUSTOM_RSS_FEEDS = "[]"
        
        # Act
        saved_count = await ingest_rss(task_run_id="test-task-run")
        
        # Assert
        assert saved_count == 1
        # Check that mock_session.execute was called to update TaskRun
        execute_calls = mock_session.execute.call_args_list
        # The update statement execution should have been called
        assert len(execute_calls) >= 2  # one for existing check, one for TaskRun update
        
        # Let's verify that one of the calls executes update on TaskRun
        task_run_updated = False
        for call in execute_calls:
            args = call[0]
            if args and hasattr(args[0], "is_update") and args[0].is_update:
                task_run_updated = True
        assert task_run_updated is True
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_newsapi_updates_task_run() -> None:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute.return_value.scalar.return_value = "running"
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(side_effect=[
        {
            "status": "ok",
            "articles": [
                {
                    "url": "https://newsapi.com/article_relevant_1",
                    "title": "Fed Hikes Interest Rates",
                    "description": "The Federal Reserve raised interest rates by 25 basis points.",
                    "content": "Full content preview here...",
                    "publishedAt": "2026-06-06T12:00:00Z",
                    "source": {"name": "Bloomberg"}
                }
            ]
        },
        {
            "status": "ok",
            "articles": [
                {
                    "url": "https://newsapi.com/article_relevant_2",
                    "title": "Fed Hikes Interest Rates",
                    "description": "The Federal Reserve raised interest rates by 25 basis points.",
                    "content": "Full content preview here...",
                    "publishedAt": "2026-06-06T12:00:00Z",
                    "source": {"name": "Bloomberg"}
                }
            ]
        }
    ])

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("src.ingest.newsapi_fetcher.settings") as mock_settings,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.newsapi_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_settings.NEWSAPI_KEY = "test_key"
        mock_settings.NEWSAPI_DOMAINS = ""

        # Act
        saved_count = await ingest_newsapi(task_run_id="test-newsapi-task-run")

        # Assert
        assert saved_count == 2
        execute_calls = mock_session.execute.call_args_list
        assert len(execute_calls) >= 3
        
        task_run_updated = False
        for call in execute_calls:
            args = call[0]
            if args and hasattr(args[0], "is_update") and args[0].is_update:
                task_run_updated = True
        assert task_run_updated is True
        mock_check.assert_not_called()



