import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.main import app

def test_trigger_briefing_endpoint():
    # 1. Arrange: Mock briefing generator
    # We mock generate_daily_briefing in briefing route triggering context
    with patch("src.api.routes.trigger.generate_daily_briefing", new_callable=AsyncMock) as mock_generate:
        # 2. Act: Call endpoint
        client = TestClient(app)
        response = client.post("/api/trigger/briefing")
        
        # 3. Assert: Verify endpoint responds and background task runs
        assert response.status_code == 200
        data = response.json()
        assert data == {"job": "briefing", "status": "started", "message": ""}
        mock_generate.assert_called_once()


@pytest.mark.asyncio
async def test_generate_daily_briefing_priority_routing():
    # Verify that generate_daily_briefing calls deep_analysis with Priority 0
    from src.analysis.briefing import generate_daily_briefing
    from src.models.schema import Insight, UrgencyEnum, SentimentEnum
    from datetime import datetime, timezone
    
    mock_session = AsyncMock()
    
    insight = Insight(
        id="ins-1", 
        subject_id="subj-1", 
        dimension_name="D1", 
        summary_en="S1", 
        summary_zh="S1", 
        urgency=UrgencyEnum.MEDIUM,
        sentiment=SentimentEnum.NEUTRAL,
        last_updated_at=datetime.now(timezone.utc)
    )
    insight.subject = MagicMock()
    insight.subject.name = "TestSubject"
    insight.subject.type = MagicMock()
    insight.subject.type.value = "ticker"
    
    from src.models.schema import InsightFact
    async def mock_execute(stmt):
        result = MagicMock()
        stmt_str = str(stmt).lower()
        if "insight_facts" in stmt_str:
            fact = InsightFact(bullet_text_en="Fact EN", bullet_text_zh="Fact ZH")
            result.scalars.return_value.all.return_value = [fact]
        else:
            result.scalars.return_value.all.return_value = [insight]
        return result
        
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    
    mock_session.commit = AsyncMock()
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with (
        patch("src.analysis.briefing.async_session_factory", mock_session_factory),
        patch("src.analysis.briefing.deep_analysis", new_callable=AsyncMock) as mock_deep_analysis
    ):
        mock_deep_analysis.return_value = '{"summary_en": "E", "summary_zh": "Z", "key_takeaways_en": [], "key_takeaways_zh": []}'
        
        # Act
        await generate_daily_briefing()
        
        # Assert
        mock_deep_analysis.assert_called_once()
        # Verify it was called with priority=0
        assert mock_deep_analysis.call_args[1].get("priority") == 0
