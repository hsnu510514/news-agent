import pytest
from datetime import datetime, timezone
from typing import Any, Sequence
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.interface import IngestionSourceType, IngestionSummary, BaseIngestAdapter
from src.ingest.pipeline import ingest_source, ingest_all, register_adapter
from src.models.schema import NewsArticle, TaskRun


class DummyArticleAdapter(BaseIngestAdapter):
    """A dummy adapter that yields custom test articles."""

    def __init__(self, items: list[NewsArticle]):
        self.items = items

    async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[Any]:
        return self.items

    async def filter_duplicates(self, items: Sequence[Any], session: AsyncSession) -> Sequence[Any]:
        # Keep everything
        return items


@pytest.mark.asyncio
async def test_ingest_source_success() -> None:
    # 1. Arrange
    # Create test articles
    article1 = NewsArticle(
        id="test-pipeline-art-1",
        url="https://test.com/pipeline-1",
        url_hash="hash-p1",
        source_type="rss",
        source_name="Test RSS",
        title="Article 1",
        is_relevant=True,
    )
    article2 = NewsArticle(
        id="test-pipeline-art-2",
        url="https://test.com/pipeline-2",
        url_hash="hash-p2",
        source_type="rss",
        source_name="Test RSS",
        title="Article 2",
        is_relevant=True,
    )
    
    adapter = DummyArticleAdapter([article1, article2])
    register_adapter(IngestionSourceType.RSS, adapter)
    
    # Mock DB Session
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    added_objs = []
    def mock_add(obj):
        added_objs.append(obj)
    mock_session.add = mock_add
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "task_runs" in stmt_str and "status" in stmt_str:
            # TaskRun status is queried and returns "running"
            res.scalar.return_value = "running"
        return res
    mock_session.execute.side_effect = mock_execute
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch("src.ingest.pipeline.async_session_factory", mock_session_factory):
        # 2. Act
        summary = await ingest_source(IngestionSourceType.RSS, task_run_id="test-run-id")
        
        # 3. Assert
        assert summary.source_type == IngestionSourceType.RSS
        assert summary.fetched_count == 2
        assert summary.saved_count == 2
        assert summary.error_message is None
        
        # Verify articles were added and committed
        assert len(added_objs) == 2
        assert added_objs[0].id == "test-pipeline-art-1"
        assert added_objs[1].id == "test-pipeline-art-2"
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_ingest_source_failure_rollback() -> None:
    # 1. Arrange
    # Create adapter that raises an exception during fetch
    class FailingAdapter(BaseIngestAdapter):
        async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[Any]:
            raise RuntimeError("Fetch failure simulation")

        async def filter_duplicates(self, items: Sequence[Any], session: AsyncSession) -> Sequence[Any]:
            return items

    adapter = FailingAdapter()
    register_adapter(IngestionSourceType.NEWSAPI, adapter)
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "task_runs" in stmt_str and "status" in stmt_str:
            res.scalar.return_value = "running"
        return res
    mock_session.execute.side_effect = mock_execute
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch("src.ingest.pipeline.async_session_factory", mock_session_factory):
        # 2. Act
        summary = await ingest_source(IngestionSourceType.NEWSAPI, task_run_id="test-fail-run-id")
        
        # 3. Assert
        assert summary.source_type == IngestionSourceType.NEWSAPI
        assert summary.fetched_count == 0
        assert summary.saved_count == 0
        assert "Fetch failure simulation" in summary.error_message
        
        # Verify rollback was called on error
        mock_session.rollback.assert_called_once()
