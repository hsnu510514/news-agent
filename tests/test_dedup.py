import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.ingest.dedup import deduplicate_news
from src.models.schema import NewsArticle

@pytest.mark.asyncio
async def test_deduplicate_news_links_duplicates() -> None:
    # 1. Arrange
    # Create canonical article and two duplicates
    article_canonical = NewsArticle(
        id="canonical-art",
        url="https://test.com/original",
        url_hash="url-hash-1",
        title="Original Story",
        fetched_at=datetime(2026, 6, 6, 12, 0, 0),
        is_relevant=True,
    )
    article_dup_url = NewsArticle(
        id="dup-url-art",
        url="https://test.com/dup-url",
        url_hash="url-hash-1",
        title="Duplicate URL Story",
        fetched_at=datetime(2026, 6, 6, 13, 0, 0),
        is_relevant=True,
    )
    
    # We will also mock content_hash duplicates
    article_canonical_content = NewsArticle(
        id="canonical-content-art",
        url="https://test.com/content-original",
        url_hash="url-hash-2",
        content_hash="content-hash-1",
        title="Original Content Story",
        fetched_at=datetime(2026, 6, 6, 12, 0, 0),
        is_relevant=True,
    )
    article_dup_content = NewsArticle(
        id="dup-content-art",
        url="https://test.com/content-dup",
        url_hash="url-hash-3",
        content_hash="content-hash-1",
        title="Duplicate Content Story",
        fetched_at=datetime(2026, 6, 6, 13, 0, 0),
        is_relevant=True,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    # We need to mock session.execute returning the duplicates for url_hash
    # and the duplicates for content_hash.
    # We will set up a side_effect based on the statement structure.
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        print(f"DEBUG SQL: {stmt_str}")
        
        # 1. Group by query for duplicates
        if "group by" in stmt_str:
            if "url_hash" in stmt_str:
                result.all.return_value = [("url-hash-1", 2)]
            elif "content_hash" in stmt_str:
                result.all.return_value = [("content-hash-1", 2)]
            else:
                result.all.return_value = []
        # 2. Fetch duplicate rows queries
        elif "where" in stmt_str:
            if "where news_articles.url_hash" in stmt_str:
                result.scalars.return_value.all.return_value = [article_canonical, article_dup_url]
            elif "where news_articles.content_hash" in stmt_str:
                result.scalars.return_value.all.return_value = [article_canonical_content, article_dup_content]
            else:
                result.scalars.return_value.all.return_value = []
        else:
            result.scalars.return_value.all.return_value = []
            
        return result

    mock_session.execute.side_effect = mock_execute

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("src.ingest.dedup.async_session_factory", mock_session_factory):
        # 2. Act
        stats = await deduplicate_news()

        # 3. Assert
        assert stats["duplicates_removed"] == 1
        assert stats["content_deduped"] == 1
        
        # Verify URL duplicate was linked to canonical
        assert article_dup_url.duplicate_of_id == "canonical-art"
        assert article_dup_url.is_relevant is False
        
        # Verify Content duplicate was linked to canonical
        assert article_dup_content.duplicate_of_id == "canonical-content-art"
        assert article_dup_content.is_relevant is False
        
        mock_session.commit.assert_called_once()
