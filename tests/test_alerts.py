import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.analysis.pipeline import process_article_sequentially
from src.models.schema import NewsArticle, LanguageEnum, Insight, Subject, InsightFact, UrgencyEnum, SentimentEnum, SubjectTypeEnum
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_flash_article_triggers_alert() -> None:
    # 1. Prepare input article
    article = NewsArticle(
        id="test-article-flash",
        title="Breaking: Sudden geopolitical escalation",
        content="A massive military conflict has started.",
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
            "subject_name": "Geopolitical",
            "subject_type": "theme",
            "dimension_name": "Military Escalation",
            "summary_en": "Military escalation has occurred.",
            "summary_zh": "发生军事升级。",
            "new_fact_bullet_en": "2026-06-06: Conflict started",
            "new_fact_bullet_zh": "2026-06-06: 冲突开始",
            "urgency": "flash",
            "sentiment": "negative",
            "tags": ["Geopolitics"],
            "detected_entities": {}
        }"""

        # Run pipeline
        await process_article_sequentially(article, session)

        # Assertions
        added_objs = [call.args[0] for call in session.add.call_args_list]
        insights = [obj for obj in added_objs if isinstance(obj, Insight)]
        assert len(insights) == 1
        insight = insights[0]
        assert insight.urgency == UrgencyEnum.FLASH


from fastapi.testclient import TestClient
from src.api.main import app
from src.storage.database import get_session

@pytest.fixture
def client_and_session():
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, mock_session
    app.dependency_overrides.clear()


def test_api_alerts_endpoint(client_and_session) -> None:
    client, mock_session = client_and_session
    
    from datetime import datetime
    subject = Subject(id="subj-1", name="War", type=SubjectTypeEnum.THEME)
    alert = Insight(
        id="alert-123",
        subject_id="subj-1",
        dimension_name="Conflict",
        summary_en="Conflict started.",
        summary_zh="冲突开始。",
        urgency=UrgencyEnum.FLASH,
        sentiment=SentimentEnum.NEGATIVE,
        tags=["War"],
        last_updated_at=datetime.now(),
    )
    alert.subject = subject
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [alert]
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert "alerts" in data
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["id"] == "alert-123"
