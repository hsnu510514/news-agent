import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import NewsArticle, LanguageEnum, Subject, Insight, InsightFact, UrgencyEnum, SentimentEnum, SubjectTypeEnum, AnalysisResult
from src.analysis.pipeline import process_article_sequentially


@pytest.mark.asyncio
async def test_process_article_sequentially_new() -> None:
    # 1. Prepare input article
    article = NewsArticle(
        id="test-article-123",
        title="Nvidia Blackwell GPU delayed by 3 months",
        content="Nvidia Blackwell architecture is facing manufacturing delays due to design issues.",
        language=LanguageEnum.EN,
        source_name="Reuters",
        is_relevant=True,
    )

    # Mock DB Session
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    session.execute.return_value.scalars.return_value.all = MagicMock(return_value=[])

    # 2. Mock core dependencies
    with (
        patch("src.analysis.pipeline.get_embedding", new_callable=AsyncMock) as mock_embed,
        patch("src.analysis.pipeline.search_embeddings_with_filter", return_value=[]) as mock_search,
        patch("src.analysis.pipeline.get_glossary_prompt_extension", new_callable=AsyncMock) as mock_glossary,
        patch("src.analysis.pipeline.classify", new_callable=AsyncMock) as mock_classify,
        patch("src.analysis.pipeline.upsert_embedding") as mock_upsert,
        patch("src.analysis.pipeline.register_detected_entities", new_callable=AsyncMock) as mock_register,
    ):
        mock_embed.return_value = [0.1] * 768
        mock_glossary.return_value = ""
        mock_classify.return_value = """{
            "action": "NEW",
            "subject_name": "NVDA",
            "subject_type": "ticker",
            "dimension_name": "Blackwell Delays",
            "summary_en": "Nvidia is facing Blackwell GPU delays.",
            "summary_zh": "英伟达Blackwell GPU面临延迟。",
            "new_fact_bullet_en": "2026-06-06: Blackwell delayed by 3 months",
            "new_fact_bullet_zh": "2026-06-06: Blackwell面临3个月延迟",
            "urgency": "high",
            "sentiment": "negative",
            "tags": ["Semiconductors", "GPU"],
            "detected_entities": {
                "companies": ["NVDA"],
                "institutions": [],
                "themes": ["GPU Delays"]
            }
        }"""

        # Run pipeline
        await process_article_sequentially(article, session)

        # Assertions
        assert mock_embed.called
        assert mock_search.called
        assert mock_classify.called
        assert mock_register.called

        # Verify session added expected objects
        added_objs = [call.args[0] for call in session.add.call_args_list]
        assert any(isinstance(obj, Subject) and obj.name == "NVDA" for obj in added_objs)
        assert any(isinstance(obj, Insight) and obj.dimension_name == "Blackwell Delays" for obj in added_objs)
        assert any(isinstance(obj, InsightFact) and "delayed by 3 months" in obj.bullet_text_en for obj in added_objs)


@pytest.mark.asyncio
async def test_process_article_sequentially_update() -> None:
    # 1. Prepare input article
    article = NewsArticle(
        id="test-article-456",
        title="Nvidia Blackwell delays confirmed by CEO",
        content="CEO confirms the delays in Blackwell GPU shipments.",
        language=LanguageEnum.EN,
        source_name="Bloomberg",
        is_relevant=True,
    )

    # Mock existing Subject and Insight
    subject = Subject(id="subj-789", name="NVDA", type=SubjectTypeEnum.TICKER)
    existing_insight = Insight(
        id="insight-abc",
        subject_id="subj-789",
        dimension_name="Blackwell Delays",
        summary_en="Nvidia Blackwell GPU delayed.",
        summary_zh="英伟达Blackwell GPU延迟。",
        urgency=UrgencyEnum.HIGH,
        sentiment=SentimentEnum.NEGATIVE,
        tags=["Semiconductors"],
    )
    existing_insight.subject = subject

    # Mock DB Session
    session = MagicMock(spec=AsyncSession)
    
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "insight_facts" in stmt_str:
            result.scalars.return_value.all.return_value = []
        elif "insights" in stmt_str:
            result.scalars.return_value.all.return_value = [existing_insight]
            result.scalar_one_or_none.return_value = existing_insight
        else:
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
        return result

    session.execute = AsyncMock(side_effect=mock_execute)

    # 2. Mock core dependencies
    with (
        patch("src.analysis.pipeline.get_embedding", new_callable=AsyncMock) as mock_embed,
        patch("src.analysis.pipeline.search_embeddings_with_filter", return_value=[{"id": "insight-abc"}]) as mock_search,
        patch("src.analysis.pipeline.get_glossary_prompt_extension", new_callable=AsyncMock) as mock_glossary,
        patch("src.analysis.pipeline.classify", new_callable=AsyncMock) as mock_classify,
        patch("src.analysis.pipeline.upsert_embedding") as mock_upsert,
        patch("src.analysis.pipeline.register_detected_entities", new_callable=AsyncMock) as mock_register,
    ):
        mock_embed.return_value = [0.1] * 768
        mock_glossary.return_value = ""
        mock_classify.return_value = """{
            "action": "UPDATE",
            "insight_id": "insight-abc",
            "updated_summary_en": "Nvidia Blackwell delays confirmed by CEO.",
            "updated_summary_zh": "英伟达CEO确认Blackwell延迟。",
            "new_fact_bullet_en": "2026-06-06: CEO confirms delays",
            "new_fact_bullet_zh": "2026-06-06: CEO确认延迟",
            "urgency": "high",
            "sentiment": "negative",
            "tags": ["Semiconductors", "GPU"],
            "detected_entities": {
                "companies": ["NVDA"]
            }
        }"""

        # Run pipeline
        await process_article_sequentially(article, session)

        # Assertions
        assert mock_embed.called
        assert mock_search.called
        assert mock_classify.called
        assert mock_register.called

        # Verify Insight was updated
        assert existing_insight.summary_en == "Nvidia Blackwell delays confirmed by CEO."
        assert existing_insight.summary_zh == "英伟达CEO确认Blackwell延迟。"

        # Verify session added the new InsightFact and AnalysisResult
        added_objs = [call.args[0] for call in session.add.call_args_list]
        assert any(isinstance(obj, InsightFact) and obj.bullet_text_en == "2026-06-06: CEO confirms delays" for obj in added_objs)
        assert any(isinstance(obj, AnalysisResult) and obj.impact_assessment == "Updated existing insight: Blackwell Delays" for obj in added_objs)
        
        # Verify upsert_embedding was called for the insight update and the raw article
        assert mock_upsert.call_count >= 2


@pytest.mark.asyncio
async def test_process_article_sequentially_no_change() -> None:
    # 1. Prepare input article
    article = NewsArticle(
        id="test-article-789",
        title="Nvidia Blackwell GPU Delayed Again",
        content="Nothing new, just repeating that Nvidia Blackwell is delayed by 3 months.",
        language=LanguageEnum.EN,
        source_name="Bloomberg",
        is_relevant=True,
    )

    # Mock DB Session
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_execute_result

    # 2. Mock core dependencies
    with (
        patch("src.analysis.pipeline.get_embedding", new_callable=AsyncMock) as mock_embed,
        patch("src.analysis.pipeline.search_embeddings_with_filter", return_value=[]) as mock_search,
        patch("src.analysis.pipeline.get_glossary_prompt_extension", new_callable=AsyncMock) as mock_glossary,
        patch("src.analysis.pipeline.classify", new_callable=AsyncMock) as mock_classify,
        patch("src.analysis.pipeline.upsert_embedding") as mock_upsert,
        patch("src.analysis.pipeline.register_detected_entities", new_callable=AsyncMock) as mock_register,
    ):
        mock_embed.return_value = [0.1] * 768
        mock_glossary.return_value = ""
        mock_classify.return_value = """{
            "action": "NO_CHANGE",
            "sentiment_score": 0.0,
            "tags": ["Semiconductors"]
        }"""

        # Run pipeline
        await process_article_sequentially(article, session)

        # Assertions
        assert mock_embed.called
        assert mock_search.called
        assert mock_classify.called

        # Verify session only added the AnalysisResult (not Insight or InsightFact)
        added_objs = [call.args[0] for call in session.add.call_args_list]
        assert len(added_objs) == 1
        analysis_res = added_objs[0]
        assert isinstance(analysis_res, AnalysisResult)
        assert analysis_res.impact_assessment == "No change in existing insights."
        assert analysis_res.urgency == UrgencyEnum.MEDIUM
        assert analysis_res.sentiment == SentimentEnum.NEUTRAL


@pytest.mark.asyncio
async def test_run_analysis_pipeline_batch() -> None:
    # Arrange
    from src.analysis.classifier import run_analysis_pipeline

    article1 = NewsArticle(
        id="art-1",
        title="Article 1",
        content="Content 1",
        published_at=datetime.now(timezone.utc),
        is_relevant=True,
    )
    article2 = NewsArticle(
        id="art-2",
        title="Article 2",
        content="Content 2",
        published_at=datetime.now(timezone.utc),
        is_relevant=True,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [article1, article2]
    mock_session.execute.return_value = mock_execute_result
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.analysis.classifier.async_session_factory", mock_session_factory),
        patch("src.analysis.classifier.process_article_sequentially", new_callable=AsyncMock) as mock_process,
    ):
        # Act
        stats = await run_analysis_pipeline(batch_size=20)

        # Assert
        assert stats == {"analyzed": 2, "failed": 0, "skipped": 0}
        assert mock_process.call_count == 2
        mock_process.assert_any_call(article1, mock_session)
        mock_process.assert_any_call(article2, mock_session)
        assert mock_session.commit.call_count == 2


@pytest.mark.asyncio
async def test_process_article_sequentially_semantic_dedup() -> None:
    # 1. Prepare input article and matched article
    article = NewsArticle(
        id="test-article-new-dup",
        title="Nvidia Blackwell Delayed",
        content="Reports say Nvidia Blackwell is delayed by 3 months.",
        language=LanguageEnum.EN,
        source_name="Bloomberg",
        is_relevant=True,
    )
    
    matched_article = NewsArticle(
        id="matched-article-canonical",
        title="Nvidia Blackwell GPU Delays Confirmed",
        content="Nvidia Blackwell delayed by 3 months due to design issues.",
        language=LanguageEnum.EN,
        source_name="Reuters",
        is_relevant=True,
    )

    # Mock DB Session
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none = MagicMock(return_value=matched_article)

    # 2. Mock Qdrant returning a match with high score
    with (
        patch("src.analysis.pipeline.get_embedding", new_callable=AsyncMock) as mock_embed,
        patch("src.analysis.pipeline.search_embeddings_with_filter", return_value=[{"id": "matched-article-canonical", "score": 0.93}]) as mock_search,
        patch("src.analysis.pipeline.classify", new_callable=AsyncMock) as mock_classify,
        patch("src.analysis.pipeline.upsert_embedding") as mock_upsert,
    ):
        mock_embed.return_value = [0.1] * 768

        # Run pipeline
        await process_article_sequentially(article, session)

        # Assertions
        assert mock_embed.called
        mock_search.assert_any_call(mock_embed.return_value, type_filter="article", limit=3)
        assert not mock_classify.called
        
        assert article.duplicate_of_id == "matched-article-canonical"
        assert article.is_relevant is False

        added_objs = [call.args[0] for call in session.add.call_args_list]
        assert len(added_objs) == 1
        analysis_res = added_objs[0]
        assert isinstance(analysis_res, AnalysisResult)
        assert analysis_res.impact_assessment == "Syndicated content of: Nvidia Blackwell GPU Delays Confirmed"
        assert analysis_res.llm_model == "semantic_dedup"

