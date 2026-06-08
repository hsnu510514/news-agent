import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.analysis.briefing import generate_daily_briefing
from src.models.schema import DailyBriefing, Insight, Subject, SubjectTypeEnum, UrgencyEnum, SentimentEnum
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_generate_daily_briefing_empty() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_execute_result
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("src.analysis.briefing.async_session_factory", mock_session_factory):
        # Act
        briefing = await generate_daily_briefing()

        # Assert
        assert briefing is not None
        assert "No major financial" in briefing.summary_en
        assert "未记录重大财务" in briefing.summary_zh
        assert mock_session.add.called
        assert mock_session.commit.called


@pytest.mark.asyncio
async def test_generate_daily_briefing_with_updates() -> None:
    # Arrange
    subject = Subject(name="Fed", type=SubjectTypeEnum.MACRO)
    insight = Insight(
        id="insight-123",
        subject_id="subj-1",
        dimension_name="Rate Escalation",
        summary_en="Fed raises rates.",
        summary_zh="美联储加息。",
        urgency=UrgencyEnum.HIGH,
        sentiment=SentimentEnum.NEGATIVE,
        tags=["Rate"],
    )
    insight.subject = subject

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "insight_facts" in stmt_str:
            result.scalars.return_value.all.return_value = []
        else:
            result.scalars.return_value.all.return_value = [insight]
        return result
        
    mock_session.execute.side_effect = mock_execute
    mock_session.commit = AsyncMock()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.analysis.briefing.async_session_factory", mock_session_factory),
        patch("src.analysis.briefing.deep_analysis", new_callable=AsyncMock) as mock_llm,
    ):
        mock_llm.return_value = """{
            "summary_en": "Cohesive summary en.",
            "summary_zh": "Cohesive summary zh.",
            "key_takeaways_en": ["Takeaway 1 en"],
            "key_takeaways_zh": ["Takeaway 1 zh"]
        }"""

        # Act
        briefing = await generate_daily_briefing()

        # Assert
        assert briefing is not None
        assert briefing.summary_en == "Cohesive summary en."
        assert briefing.summary_zh == "Cohesive summary zh."
        assert briefing.key_takeaways_en == ["Takeaway 1 en"]
        assert briefing.key_takeaways_zh == ["Takeaway 1 zh"]
        assert mock_llm.called
        assert mock_session.add.called
        assert mock_session.commit.called


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


def test_api_briefings_endpoints(client_and_session) -> None:
    client, mock_session = client_and_session
    
    from datetime import datetime
    briefing = DailyBriefing(
        id="briefing-123",
        summary_en="Cohesive summary en.",
        summary_zh="Cohesive summary zh.",
        key_takeaways_en=["Takeaway 1"],
        key_takeaways_zh=["Takeaway 1 zh"],
        generated_at=datetime.now(),
    )
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = briefing
    mock_execute_result.scalars.return_value.all.return_value = [briefing]
    mock_session.execute.return_value = mock_execute_result

    # 1. GET /api/briefings/latest
    response = client.get("/api/briefings/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "briefing-123"
    assert data["summary_en"] == "Cohesive summary en."
    
    # 2. GET /api/briefings
    response = client.get("/api/briefings")
    assert response.status_code == 200
    data = response.json()
    assert len(data["briefings"]) == 1
    assert data["briefings"][0]["id"] == "briefing-123"

