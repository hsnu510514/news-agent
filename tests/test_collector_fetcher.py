import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from src.core.config import settings
from src.models.schema import SourceTypeEnum, NewsArticle, LanguageEnum

def test_collector_config_defaults() -> None:
    assert settings.COLLECTOR_BASE_URL == "https://ho4s8ws8088wkss0c4c8cc0s.runrunstopstop.run"
    assert settings.COLLECTOR_FETCH_INTERVAL_MINUTES == 30
    assert settings.ENABLED_COLLECTOR_SOURCES == ""

def test_collector_source_type_enum() -> None:
    assert "collector" in SourceTypeEnum.__members__.values()
    assert SourceTypeEnum.COLLECTOR == "collector"

@pytest.mark.asyncio
async def test_ingest_collector_initial() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    
    mock_result = MagicMock()
    mock_result.scalar.return_value = None  # No watermark
    mock_result.scalar_one_or_none.return_value = None  # Article doesn't exist
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "items": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_name": "Bloomberg Markets",
                "guid": "https://bloomberg.com/markets-1",
                "url": "https://bloomberg.com/markets-1",
                "title": "Fed Signals Rate Cut",
                "description": "Short description of rate cut",
                "content": "<p>Full content of rate cut</p>",
                "author": "Bloomberg",
                "categories": ["finance"],
                "published_at": "2026-06-12T07:00:00Z",
                "fetched_at": "2026-06-12T07:05:00Z",
                "raw_json": {}
            }
        ],
        "limit": 100,
        "offset": 0
    })

    from src.ingest.collector_fetcher import ingest_collector

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get,
        patch("src.ingest.collector_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_check.return_value = True
        
        # Act
        saved_count = await ingest_collector()
        
        # Assert
        assert saved_count == 1
        
        # Verify API request URL and parameters (no 'since' because watermark was None)
        called_args, called_kwargs = mock_get.call_args
        params = called_kwargs.get("params") or (called_args[1] if len(called_args) > 1 else {})
        assert "since" not in params
        assert params["limit"] == 100
        
        # Verify db insert
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert isinstance(article, NewsArticle)
        assert article.title == "Fed Signals Rate Cut"
        assert article.source_type == SourceTypeEnum.COLLECTOR
        assert article.source_name == "Bloomberg"  # Normalized from "Bloomberg Markets"
        assert article.language == LanguageEnum.EN
        assert article.fetched_at == datetime.fromisoformat("2026-06-12T07:05:00Z")
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_collector_incremental() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    
    mock_result = MagicMock()
    # Watermark = June 12, 2026 07:05:00 UTC
    watermark = datetime(2026, 6, 12, 7, 5, 0, tzinfo=timezone.utc)
    mock_result.scalar.return_value = watermark
    mock_result.scalar_one_or_none.return_value = None  # Article doesn't exist
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "items": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "source_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_name": "Bloomberg Markets",
                "guid": "https://bloomberg.com/markets-2",
                "url": "https://bloomberg.com/markets-2",
                "title": "Nvidia Blackwell GPU Shipping",
                "description": "Short description of GPU shipping",
                "content": "<p>Full content of GPU shipping</p>",
                "author": "Bloomberg",
                "categories": ["tech"],
                "published_at": "2026-06-12T08:00:00Z",
                "fetched_at": "2026-06-12T08:05:00Z",
                "raw_json": {}
            }
        ],
        "limit": 100,
        "offset": 0
    })

    from src.ingest.collector_fetcher import ingest_collector

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get,
        patch("src.ingest.collector_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_check.return_value = True
        
        # Act
        saved_count = await ingest_collector()
        
        # Assert
        assert saved_count == 1
        
        # Verify API request URL and parameters (with 'since' watermark)
        called_args, called_kwargs = mock_get.call_args
        params = called_kwargs.get("params") or (called_args[1] if len(called_args) > 1 else {})
        assert params["since"] == watermark.isoformat()
        assert params["limit"] == 100
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_collector_normalization() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "items": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "source_name": "财新-首页新闻",
                "url": "https://caixin.com/article-3",
                "title": "中国5月CPI数据出炉",
                "description": "中国5月CPI同比上涨0.3%",
                "fetched_at": "2026-06-12T07:05:00Z"
            }
        ],
        "limit": 100,
        "offset": 0
    })

    from src.ingest.collector_fetcher import ingest_collector

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.collector_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_check.return_value = True
        
        # Act
        await ingest_collector()
        
        # Assert
        added_objs = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added_objs) == 1
        article = added_objs[0]
        assert article.source_name == "财新网"
        assert article.language == LanguageEnum.ZH


@pytest.mark.asyncio
async def test_ingest_collector_filtering() -> None:
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "items": [
            {
                "id": "item-1",
                "source_name": "Bloomberg Markets",
                "url": "https://bloomberg.com/1",
                "title": "Fed rate cut decisions",
                "fetched_at": "2026-06-12T07:05:00Z"
            },
            {
                "id": "item-2",
                "source_name": "TechCrunch",
                "url": "https://techcrunch.com/2",
                "title": "New startup raises funding",
                "fetched_at": "2026-06-12T07:06:00Z"
            }
        ],
        "limit": 100,
        "offset": 0
    })

    from src.ingest.collector_fetcher import ingest_collector

    with (
        patch("src.ingest.pipeline.async_session_factory", mock_session_factory),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response),
        patch("src.ingest.collector_fetcher.check_relevance", new_callable=AsyncMock, create=True) as mock_check,
    ):
        mock_check.return_value = True
        
        # Configure whitelist filtering
        with patch.object(settings, "ENABLED_COLLECTOR_SOURCES", "Bloomberg Markets"):
            # Act
            saved_count = await ingest_collector()
            
            # Assert
            # Only item-1 should be saved because it is in ENABLED_COLLECTOR_SOURCES
            assert saved_count == 1
            added_objs = [call.args[0] for call in mock_session.add.call_args_list]
            assert len(added_objs) == 1
            assert added_objs[0].source_name == "Bloomberg"


def test_collector_scheduler_job_registered() -> None:
    from src.scheduler.jobs import DEFAULT_JOBS
    collector_job = next((job for job in DEFAULT_JOBS if job["id"] == "collector_news"), None)
    assert collector_job is not None
    assert collector_job["name"] == "Collector Ingest"  # Updated name
    assert collector_job["trigger_type"] == "interval"
    assert collector_job["schedule_value"] == str(settings.COLLECTOR_FETCH_INTERVAL_MINUTES)


@pytest.mark.asyncio
async def test_run_job_wrapper_collector() -> None:
    from src.scheduler.jobs import run_job_wrapper
    from src.models.schema import JobConfig
    
    mock_job_func = AsyncMock()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    mock_job_config = JobConfig(id="collector_news", name="Collector Ingest", enabled=True, trigger_type="interval", schedule_value="30")
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "select" in stmt_str and "job_configs" in stmt_str:
            result.scalar_one_or_none.return_value = mock_job_config
        return result
    mock_session.execute.side_effect = mock_execute

    with (
        patch("src.scheduler.jobs._job_collector", mock_job_func),
        patch("src.scheduler.jobs.async_session_factory", mock_session_factory)
    ):
        await run_job_wrapper("collector_news")
        mock_job_func.assert_called_once()


def test_get_collector_sources_endpoint() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "sources": [
            {"name": "Bloomberg Markets", "enabled": True}
        ]
    })
    
    client = TestClient(app)
    
    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get,
        patch("src.api.routes.system.settings") as mock_settings
    ):
        mock_settings.COLLECTOR_BASE_URL = "http://localhost:8080"
        
        response = client.get("/api/system/collector-sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert len(data["sources"]) == 1
        assert data["sources"][0]["name"] == "Bloomberg Markets"
        assert mock_get.call_args[0][0] == "http://localhost:8080/api/sources"


def test_models_endpoint_with_collector_sources() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    
    client = TestClient(app)
    
    # Verify GET /api/system/models includes ENABLED_COLLECTOR_SOURCES
    response = client.get("/api/system/models")
    assert response.status_code == 200
    data = response.json()
    assert "ENABLED_COLLECTOR_SOURCES" in data["allocations"]
