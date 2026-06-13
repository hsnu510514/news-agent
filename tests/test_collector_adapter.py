import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.collector_fetcher import CollectorIngestAdapter
from src.models.schema import NewsArticle, LanguageEnum, SourceTypeEnum


@pytest.mark.asyncio
async def test_collector_adapter_fetch_no_watermark() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = None  # No watermark
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "id": "item-1",
                "source_id": "source-1",
                "source_name": "Bloomberg Markets",
                "url": "https://bloomberg.com/markets-1",
                "title": "Fed Signals Rate Cut",
                "description": "Short description",
                "content": "<p>Full content</p>",
                "author": "Bloomberg",
                "categories": ["finance"],
                "published_at": "2026-06-12T07:00:00Z",
                "fetched_at": "2026-06-12T07:05:00Z",
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    adapter = CollectorIngestAdapter()

    with (
        patch("src.ingest.collector_fetcher.settings") as mock_settings,
    ):
        mock_settings.COLLECTOR_BASE_URL = "https://collector.api"
        mock_settings.RSSHUB_ACCESS_KEY = "test_key"
        mock_settings.ENABLED_COLLECTOR_SOURCES = ""

        # Act
        articles = await adapter.fetch(mock_client, mock_session)

        # Assert
        assert len(articles) == 1
        art = articles[0]
        assert isinstance(art, NewsArticle)
        assert art.title == "Fed Signals Rate Cut"
        assert art.url == "https://bloomberg.com/markets-1"
        assert art.source_name == "Bloomberg"
        assert art.language == LanguageEnum.EN
        assert art.source_type == SourceTypeEnum.COLLECTOR
        assert art.published_at == datetime(2026, 6, 12, 7, 0, 0, tzinfo=timezone.utc)
        assert art.fetched_at == datetime(2026, 6, 12, 7, 5, 0, tzinfo=timezone.utc)

        # Verify query had no watermark
        called_args, called_kwargs = mock_client.get.call_args
        params = called_kwargs.get("params")
        assert "since" not in params
        assert params["limit"] == 100
        assert params["offset"] == 0
        assert called_kwargs.get("headers")["Authorization"] == "Bearer test_key"


@pytest.mark.asyncio
async def test_collector_adapter_fetch_with_watermark() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    watermark = datetime(2026, 6, 12, 7, 5, 0, tzinfo=timezone.utc)
    mock_result.scalar.return_value = watermark
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": []
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    adapter = CollectorIngestAdapter()

    with (
        patch("src.ingest.collector_fetcher.settings") as mock_settings,
    ):
        mock_settings.COLLECTOR_BASE_URL = "https://collector.api"
        mock_settings.RSSHUB_ACCESS_KEY = ""
        mock_settings.ENABLED_COLLECTOR_SOURCES = ""

        # Act
        articles = await adapter.fetch(mock_client, mock_session)

        # Assert
        assert len(articles) == 0
        called_args, called_kwargs = mock_client.get.call_args
        params = called_kwargs.get("params")
        assert params["since"] == watermark.isoformat()


@pytest.mark.asyncio
async def test_collector_adapter_filter_duplicates() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [("existing_hash_1",)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    adapter = CollectorIngestAdapter()

    articles = [
        NewsArticle(url="https://a.com", url_hash="existing_hash_1", title="A"),
        NewsArticle(url="https://b.com", url_hash="new_hash_2", title="B"),
        NewsArticle(url="https://c.com", url_hash="new_hash_2", title="C"),
    ]

    # Act
    filtered = await adapter.filter_duplicates(articles, mock_session)

    # Assert
    assert len(filtered) == 1
    assert filtered[0].url_hash == "new_hash_2"
    mock_session.execute.assert_called_once()
