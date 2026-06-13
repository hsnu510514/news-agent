import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.api.main import app
from src.storage.database import get_session
from src.models.schema import SubjectTypeEnum

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

# Need to import AsyncSession for typing
from sqlalchemy.ext.asyncio import AsyncSession

def test_api_top_tags_endpoint(client_and_session) -> None:
    client, mock_session = client_and_session
    
    # Mock database output for top tags query
    # The query is expected to return rows with (tag, count)
    mock_row1 = ("Semiconductors", 25)
    mock_row2 = ("AI", 18)

    mock_execute_result = MagicMock()
    mock_execute_result.all.return_value = [mock_row1, mock_row2]
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/insights/top-tags?subject_type=ticker")
    assert response.status_code == 200
    data = response.json()
    assert "tags" in data
    assert data["tags"] == ["Semiconductors", "AI"]


def test_api_insights_list_filtering_and_pagination(client_and_session) -> None:
    client, mock_session = client_and_session

    from datetime import datetime
    from src.models.schema import Insight, Subject, SentimentEnum, UrgencyEnum
    
    # Mock return rows
    subject = Subject(id="subj-1", name="NVDA", type=SubjectTypeEnum.TICKER, tags=["Semiconductors"])
    insight = Insight(
        id="insight-1",
        subject_id="subj-1",
        dimension_name="Blackwell GPU",
        summary_en="Blackwell GPU is delayed.",
        summary_zh="Blackwell GPU延迟。",
        urgency=UrgencyEnum.HIGH,
        sentiment=SentimentEnum.NEGATIVE,
        tags=["GPU"],
        last_updated_at=datetime.now(),
    )
    insight.subject = subject
    insight.facts = []

    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [insight]
    mock_session.execute.return_value = mock_execute_result

    # Make request with all query parameters
    response = client.get("/api/insights?subject_type=ticker&tag=GPU&q=Blackwell&limit=5&offset=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "insight-1"

    # Verify that mock_session.execute was called with the compiled query containing filters
    assert mock_session.execute.called
    stmt = mock_session.execute.call_args[0][0]
    stmt_str = str(stmt).lower()
    
    # Assert query structure (must join subjects and apply where clauses)
    assert "join subjects" in stmt_str
    assert "subjects.type" in stmt_str
    assert "like" in stmt_str or "ilike" in stmt_str
    assert "limit" in stmt_str
    assert "offset" in stmt_str


def test_api_divergence_endpoint(client_and_session) -> None:
    client, mock_session = client_and_session

    from src.models.schema import Subject, Insight, SentimentEnum, UrgencyEnum
    
    # 1. Create mock duplicate subjects
    subj1 = Subject(id="subj-1", name="Focuslight Technologies", type=SubjectTypeEnum.TICKER)
    subj2 = Subject(id="subj-2", name="Focuslight Tech", type=SubjectTypeEnum.TICKER)
    
    # 2. Create mock duplicate insights under the same subject
    subj3 = Subject(id="subj-3", name="AAPL", type=SubjectTypeEnum.TICKER)
    ins1 = Insight(
        id="ins-1",
        subject_id="subj-3",
        dimension_name="Q1 2026 Earnings Results",
        summary_en="Apple announced strong Q1 2026 earnings results.",
        summary_zh="苹果公布了强劲的2026年第一季度收益结果。",
        urgency=UrgencyEnum.MEDIUM,
        sentiment=SentimentEnum.POSITIVE,
        tags=[],
    )
    ins1.subject = subj3
    
    ins2 = Insight(
        id="ins-2",
        subject_id="subj-3",
        dimension_name="Q1 2026 Financial Results",
        summary_en="Apple announced strong Q1 2026 financial results.",
        summary_zh="苹果公布了强劲的2026年第一季度财务结果。",
        urgency=UrgencyEnum.MEDIUM,
        sentiment=SentimentEnum.POSITIVE,
        tags=[],
    )
    ins2.subject = subj3

    # Setup database mocks for the new cache-based endpoint query
    from src.models.schema import PotentialDuplicate
    
    mock_dup_subj = PotentialDuplicate(
        entity_type="subject",
        id1="subj-1",
        id2="subj-2",
        similarity=0.83,
        status="pending"
    )
    mock_dup_ins = PotentialDuplicate(
        entity_type="insight",
        id1="ins-1",
        id2="ins-2",
        similarity=0.95,
        status="pending"
    )

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "potential_duplicates" in stmt_str:
            if "insight" in stmt_str:
                # Returns (PotentialDuplicate, Ins1, Ins2, Subject)
                res.all.return_value = [(mock_dup_ins, ins1, ins2, subj3)]
            else:
                # Returns (PotentialDuplicate, Subj1, Subj2)
                res.all.return_value = [(mock_dup_subj, subj1, subj2)]
        else:
            res.all.return_value = []
            res.scalars.return_value.all.return_value = []
        return res
 
    mock_session.execute = AsyncMock(side_effect=mock_execute)
 
    response = client.get("/api/insights/divergence")
    assert response.status_code == 200
    data = response.json()
 
    assert "subjects" in data
    assert "insights" in data
 
    # Verify Subject duplicate detected
    assert len(data["subjects"]) == 1
    assert data["subjects"][0]["name1"] == "Focuslight Technologies"
    assert data["subjects"][0]["name2"] == "Focuslight Tech"
 
    # Verify Insight duplicate detected
    assert len(data["insights"]) == 1
    assert data["insights"][0]["subject_name"] == "AAPL"
    assert data["insights"][0]["dim1"] == "Q1 2026 Earnings Results"
    assert data["insights"][0]["dim2"] == "Q1 2026 Financial Results"
