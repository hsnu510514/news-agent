import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import NewsArticle, LanguageEnum, Subject, Insight, InsightFact
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
