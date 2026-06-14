import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.models.schema import NewsArticle, TaskRun
from src.ingest.preprocessing import run_preprocessing_pipeline

@pytest.mark.asyncio
async def test_preprocessing_pipeline_success() -> None:
    # Arrange
    # 1. Mock articles in database
    art1 = NewsArticle(
        id="art-1",
        title="Relevant AI News",
        content="AI agents are taking over the coding world.",
        is_relevant=None,
        published_at=datetime.now(timezone.utc)
    )
    art2 = NewsArticle(
        id="art-2",
        title="Irrelevant Political Debates",
        content="General discussions about election polls.",
        is_relevant=None,
        published_at=datetime.now(timezone.utc)
    )
    art3 = NewsArticle(
        id="art-3",
        title="Duplicate AI News",
        content="AI agents are taking over the coding world.",
        is_relevant=None,
        published_at=datetime.now(timezone.utc)
    )

    articles = [art1, art2, art3]

    # Mock Session and session execution
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Stub executing queries
    # First query retrieves pending articles
    # Subsequent query in deduplication looks for existing duplicate content hash
    # We want to return the pending articles on the first query and empty list on subsequent queries.
    called_count = 0
    from src.ingest.preprocessing import hash_content
    hash1 = hash_content(art1.content)
    
    async def side_effect_execute(stmt, *args, **kwargs):
        nonlocal called_count
        stmt_str = str(stmt).lower()
        mock_res = MagicMock()
        
        # Check if it's the pending query (fetching where is_relevant is null)
        if "is_relevant is null" in stmt_str or "is_relevant.is_(none)" in stmt_str or "is_relevant" in stmt_str and "hash" not in stmt_str:
            mock_scalars = MagicMock()
            if called_count == 0:
                mock_scalars.all.return_value = articles
                called_count += 1
            else:
                mock_scalars.all.return_value = []
            mock_res.scalars.return_value = mock_scalars
        elif "content_hash" in stmt_str:
            # Check the compiled param for content_hash_1
            try:
                params = stmt.compile().params
                param_hash = params.get("content_hash_1")
            except Exception:
                param_hash = None
                
            if param_hash == hash1 and art1.is_relevant is not None:
                mock_res.scalar_one_or_none.return_value = art1
            else:
                mock_res.scalar_one_or_none.return_value = None
        else:
            mock_res.scalar_one_or_none.return_value = None
            mock_res.scalars.return_value.first.return_value = None
        return mock_res

    mock_session.execute.side_effect = side_effect_execute

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.ingest.preprocessing.async_session_factory", mock_session_factory),
        patch("src.ingest.preprocessing.check_relevance", new_callable=AsyncMock) as mock_check,
    ):
        # relevance returns True for art1, False for art2.
        # art3 should not trigger check_relevance because it is a content duplicate of art1.
        async def check_relevance_side_effect(title, desc):
            if "Relevant" in title:
                return True
            return False
        mock_check.side_effect = check_relevance_side_effect

        # Act
        stats = await run_preprocessing_pipeline()

        # Assert
        assert stats["processed"] == 3
        assert stats["duplicates"] == 1
        assert stats["relevant"] == 1
        assert stats["irrelevant"] == 1

        # Check art1 updates
        assert art1.is_relevant is True
        assert art1.content_hash is not None
        
        # Check art2 updates
        assert art2.is_relevant is False
        assert art2.content is None  # content cleared
        
        # Check art3 updates
        assert art3.is_relevant is False
        assert art3.duplicate_of_id == "art-1"
        assert art3.content is None  # content cleared

        # check_relevance should have been called exactly twice: once for art1, once for art2
        assert mock_check.call_count == 2
        mock_check.assert_any_call("Relevant AI News", "AI agents are taking over the coding world.")
        mock_check.assert_any_call("Irrelevant Political Debates", "General discussions about election polls.")
        
        # Commits should happen per article (3 commits)
        assert mock_session.commit.call_count == 3
