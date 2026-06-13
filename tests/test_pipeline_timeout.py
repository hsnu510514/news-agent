import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.schema import NewsArticle
from src.core.config import settings
from src.analysis.classifier import run_analysis_pipeline


@pytest.mark.asyncio
async def test_run_analysis_pipeline_timeout_abort():
    # Arrange: 3 articles
    art1 = NewsArticle(id="art-1", title="A1", content="C1", published_at=datetime.now(timezone.utc), is_relevant=True)
    art2 = NewsArticle(id="art-2", title="A2", content="C2", published_at=datetime.now(timezone.utc), is_relevant=True)
    art3 = NewsArticle(id="art-3", title="A3", content="C3", published_at=datetime.now(timezone.utc), is_relevant=True)

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()

    # We mock execute to return our list of articles on the first fetch
    # And return an empty list on the second fetch (meaning no more backlog)
    mock_execute_result = MagicMock()
    mock_execute_result.scalar.return_value = "running"
    # On the first iteration, it returns art1, art2, art3
    # On subsequent iterations, it returns empty (in case loop tries to fetch again)
    mock_execute_result.scalars.return_value.all.side_effect = [
        [art1, art2, art3],
        []
    ]
    mock_session.execute.return_value = mock_execute_result
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # We mock datetime to simulate elapsed time.
    # The pipeline will start at t0.
    # For art1, it's t0 + 1 min (below timeout of 2 mins).
    # For art2, it's t0 + 3 mins (above timeout of 2 mins).
    t0 = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    # We patch settings.MAX_ANALYSIS_DURATION_MINUTES to 2 minutes
    # and settings.ANALYSIS_BATCH_SIZE to 20
    with patch.object(settings, "MAX_ANALYSIS_DURATION_MINUTES", 2):
        # We mock datetime.now to return:
        # 1. t0 (on start_time)
        # 2. t0 (on timeout check before batch)
        # 3. t0 (on cutoff calculation)
        # 4. t0 + 1 min (before processing art1)
        # 5. t0 + 3 min (before processing art2 - timeout!)
        # 6. t0 + 3 min (on TaskRun update)
        mock_now = MagicMock(side_effect=[
            t0,                 # start_time
            t0,                 # timeout check before batch
            t0,                 # cutoff calculation
            t0 + timedelta(minutes=1),  # before art1
            t0 + timedelta(minutes=3),  # before art2 -> should trigger timeout!
            t0 + timedelta(minutes=3)   # task run end_time
        ])
        
        # Mock process_article_sequentially
        processed_articles = []
        async def mock_process(art, session):
            processed_articles.append(art.id)
            return None

        # Patch datetime to control our mock time source
        with (
            patch("src.analysis.classifier.async_session_factory", mock_session_factory),
            patch("src.analysis.classifier.process_article_sequentially", mock_process),
            patch("src.analysis.classifier.datetime") as mock_datetime
        ):
            mock_datetime.now = mock_now
            # Mock datetime.now to also accept tz argument or direct calls
            mock_datetime.now.side_effect = mock_now.side_effect

            # Act: run pipeline
            stats = await run_analysis_pipeline(batch_size=20, task_run_id="test-run-timeout")

            # Assert:
            # We expect only art1 to be processed because before art2, we exceed 2 minutes.
            assert processed_articles == ["art-1"]
            assert stats == {"analyzed": 1, "failed": 0, "skipped": 0, "status": "timeout"}

            # Verify that TaskRun was updated to "timeout" in the database
            update_calls = []
            for call_arg in mock_session.execute.call_args_list:
                stmt = call_arg[0][0]
                stmt_str = str(stmt).lower()
                if "update" in stmt_str and "task_runs" in stmt_str:
                    update_calls.append(stmt)

            # We expect an update setting status to "timeout"
            timeout_updated = False
            for stmt in update_calls:
                params = stmt.compile().params
                if params.get("status_1") == "timeout" or any(v == "timeout" for v in params.values()):
                    timeout_updated = True
                    break
            assert timeout_updated, "TaskRun status was not updated to 'timeout' in DB"
