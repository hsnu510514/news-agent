import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.schema import NewsArticle
from src.core.llm import DailyQuotaExhaustedError
from src.analysis.classifier import run_analysis_pipeline

@pytest.mark.asyncio
async def test_run_analysis_pipeline_concurrency_lock():
    # Arrange: Mock session and pipeline execution
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [
        NewsArticle(id="art-1", title="Art 1", content="Content", published_at=datetime.now(timezone.utc), is_relevant=True)
    ]
    mock_session.execute.return_value = mock_execute_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock pipeline processing to simulate a slow run (holding the lock)
    async def mock_slow_process(art, session):
        await asyncio.sleep(0.5)

    with (
        patch("src.analysis.classifier.async_session_factory", mock_session_factory),
        patch("src.analysis.classifier.process_article_sequentially", mock_slow_process)
    ):
        # Act: start the first run in the background
        task1 = asyncio.create_task(run_analysis_pipeline(batch_size=20))
        
        # Give task1 a tiny slice to acquire the lock and enter execution
        await asyncio.sleep(0.05)
        
        # Now trigger the pipeline a second time concurrently
        stats2 = await run_analysis_pipeline(batch_size=20)
        
        # Wait for task1 to complete
        stats1 = await task1
        
        # Assert: the second run should have skipped execution
        assert stats1 == {"analyzed": 1, "failed": 0, "skipped": 0}
        assert stats2 == {"analyzed": 0, "failed": 0, "skipped": 0, "reason": "already_running"}


@pytest.mark.asyncio
async def test_run_analysis_pipeline_checkpoint_commits():
    # Arrange: 3 articles
    art1 = NewsArticle(id="art-1", title="A1", content="C1", published_at=datetime.now(timezone.utc), is_relevant=True)
    art2 = NewsArticle(id="art-2", title="A2", content="C2", published_at=datetime.now(timezone.utc), is_relevant=True)
    art3 = NewsArticle(id="art-3", title="A3", content="C3", published_at=datetime.now(timezone.utc), is_relevant=True)
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [art1, art2, art3]
    mock_session.execute.return_value = mock_execute_result
    
    # Track commits
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock process_article_sequentially to succeed on first, fail on second, succeed on third
    async def mock_process(art, session):
        if art.id == "art-2":
            raise Exception("Transient error")
        return None

    with (
        patch("src.analysis.classifier.async_session_factory", mock_session_factory),
        patch("src.analysis.classifier.process_article_sequentially", mock_process)
    ):
        # Act
        stats = await run_analysis_pipeline(batch_size=20)
        
        # Assert
        assert stats == {"analyzed": 2, "failed": 1, "skipped": 0}
        # Commit should be called per successfully processed article
        assert mock_session.commit.call_count == 2


@pytest.mark.asyncio
async def test_run_analysis_pipeline_quota_exhaustion_abort():
    # Arrange: 3 articles
    art1 = NewsArticle(id="art-1", title="A1", content="C1", published_at=datetime.now(timezone.utc), is_relevant=True)
    art2 = NewsArticle(id="art-2", title="A2", content="C2", published_at=datetime.now(timezone.utc), is_relevant=True)
    art3 = NewsArticle(id="art-3", title="A3", content="C3", published_at=datetime.now(timezone.utc), is_relevant=True)
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [art1, art2, art3]
    mock_session.execute.return_value = mock_execute_result
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock process_article_sequentially: first succeeds, second raises DailyQuotaExhaustedError
    call_tracker = []
    async def mock_process(art, session):
        call_tracker.append(art.id)
        if art.id == "art-2":
            raise DailyQuotaExhaustedError("Quota reached!")
        return None

    with (
        patch("src.analysis.classifier.async_session_factory", mock_session_factory),
        patch("src.analysis.classifier.process_article_sequentially", mock_process)
    ):
        # Act
        stats = await run_analysis_pipeline(batch_size=20)
        
        # Assert
        assert stats == {"analyzed": 1, "failed": 1, "skipped": 0}
        # Commit should only be called once (for art-1)
        assert mock_session.commit.call_count == 1
        # The loop should have aborted after art-2, meaning art-3 was never processed
        assert call_tracker == ["art-1", "art-2"]


@pytest.mark.asyncio
async def test_run_analysis_pipeline_updates_task_run_progress():
    # Arrange: 3 articles
    art1 = NewsArticle(id="art-1", title="A1", content="C1", published_at=datetime.now(timezone.utc), is_relevant=True)
    art2 = NewsArticle(id="art-2", title="A2", content="C2", published_at=datetime.now(timezone.utc), is_relevant=True)
    art3 = NewsArticle(id="art-3", title="A3", content="C3", published_at=datetime.now(timezone.utc), is_relevant=True)
    
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [art1, art2, art3]
    mock_session.execute.return_value = mock_execute_result
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock process_article_sequentially: first succeeds, second fails, third succeeds
    async def mock_process(art, session):
        if art.id == "art-2":
            raise Exception("Fail art-2")
        return None

    with (
        patch("src.analysis.classifier.async_session_factory", mock_session_factory),
        patch("src.analysis.classifier.process_article_sequentially", mock_process)
    ):
        # Act: run the pipeline with a task_run_id
        stats = await run_analysis_pipeline(batch_size=20, task_run_id="test-run-123")
        
        # Assert: pipeline returned stats
        assert stats == {"analyzed": 2, "failed": 1, "skipped": 0}
        
        # Verify execute calls on session include updates to TaskRun
        update_calls = []
        for call_arg in mock_session.execute.call_args_list:
            stmt = call_arg[0][0]
            stmt_str = str(stmt).lower()
            if "update" in stmt_str and "task_runs" in stmt_str:
                update_calls.append(stmt)
                
        # Total count is updated once, and then progress is updated per article (3 articles)
        # So we expect 4 update calls to task_runs total
        assert len(update_calls) == 4
        
        # Check first update call updates total_count
        first_params = update_calls[0].compile().params
        first_total = next(v for k, v in first_params.items() if "total_count" in k)
        assert first_total == 3
        
        # Check final update call updates processed_count to 2, failed_count to 1
        final_params = update_calls[-1].compile().params
        final_processed = next(v for k, v in final_params.items() if "processed_count" in k)
        final_failed = next(v for k, v in final_params.items() if "failed_count" in k)
        assert final_processed == 2
        assert final_failed == 1

