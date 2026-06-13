import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.api.main import app
from src.storage.database import get_session
from src.models.schema import NewsArticle, LanguageEnum, SourceTypeEnum, AnalysisResult, UrgencyEnum, SentimentEnum

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

def test_list_news_returns_nested_analysis(client_and_session) -> None:
    client, mock_session = client_and_session
    
    # Create an analyzed article
    analyzed_article = NewsArticle(
        id="analyzed-art-1",
        title="Analyzed Article",
        url="https://test.com/analyzed",
        source_type=SourceTypeEnum.RSS,
        source_name="Reuters",
        language=LanguageEnum.EN,
        published_at=datetime.now(),
        fetched_at=datetime.now(),
        duplicate_of_id=None,
    )
    analysis = AnalysisResult(
        id="analysis-1",
        article_id="analyzed-art-1",
        urgency=UrgencyEnum.HIGH,
        sentiment=SentimentEnum.POSITIVE,
        sentiment_score=0.8,
        topics=["Market"],
        companies_mentioned=["AAPL"],
        summary_en="An analyzed article summary.",
        summary_zh="分析的文章摘要。",
        impact_assessment="High impact.",
        llm_model="test-model",
        analyzed_at=datetime.now(),
    )
    analyzed_article.analysis = [analysis]
    
    # Create a pending article
    pending_article = NewsArticle(
        id="pending-art-2",
        title="Pending Article",
        url="https://test.com/pending",
        source_type=SourceTypeEnum.RSS,
        source_name="Bloomberg",
        language=LanguageEnum.EN,
        published_at=datetime.now(),
        fetched_at=datetime.now(),
        duplicate_of_id=None,
    )
    pending_article.analysis = []
    
    mock_execute_result = MagicMock()
    # Mock total count scalar
    mock_execute_result.scalar_one.return_value = 2
    # Mock results scalars returning both articles
    mock_execute_result.scalars.return_value.all.return_value = [analyzed_article, pending_article]
    mock_session.execute.return_value = mock_execute_result

    response = client.get("/api/news")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    
    # Verify analyzed article nests analysis data
    analyzed_item = next(item for item in data["items"] if item["id"] == "analyzed-art-1")
    assert analyzed_item["analysis"] is not None
    assert analyzed_item["analysis"]["id"] == "analysis-1"
    assert analyzed_item["analysis"]["urgency"] == "high"
    assert analyzed_item["analysis"]["sentiment"] == "positive"
    assert analyzed_item["analysis"]["sentiment_score"] == 0.8
    assert analyzed_item["analysis"]["topics"] == ["Market"]
    assert analyzed_item["analysis"]["companies_mentioned"] == ["AAPL"]
    
    # Verify pending article has null analysis
    pending_item = next(item for item in data["items"] if item["id"] == "pending-art-2")
    assert pending_item["analysis"] is None

def test_list_news_filters_and_multi_field_search(client_and_session) -> None:
    client, mock_session = client_and_session
    
    analyzed_article = NewsArticle(
        id="analyzed-art-1",
        title="Analyzed Article",
        url="https://test.com/analyzed",
        source_type=SourceTypeEnum.RSS,
        source_name="Reuters",
        language=LanguageEnum.EN,
        published_at=datetime.now(),
        fetched_at=datetime.now(),
        duplicate_of_id=None,
    )
    analysis = AnalysisResult(
        id="analysis-1",
        article_id="analyzed-art-1",
        urgency=UrgencyEnum.HIGH,
        sentiment=SentimentEnum.POSITIVE,
        sentiment_score=0.8,
        topics=["Market"],
        companies_mentioned=["AAPL"],
        summary_en="Specialized market overview summary.",
        summary_zh="分析的文章摘要。",
        impact_assessment="High impact.",
        llm_model="test-model",
        analyzed_at=datetime.now(),
    )
    analyzed_article.analysis = [analysis]
    
    pending_article = NewsArticle(
        id="pending-art-2",
        title="Pending Article",
        url="https://test.com/pending",
        source_type=SourceTypeEnum.RSS,
        source_name="Bloomberg",
        language=LanguageEnum.EN,
        published_at=datetime.now(),
        fetched_at=datetime.now(),
        duplicate_of_id=None,
    )
    pending_article.analysis = []
    
    mock_execute_result = MagicMock()
    # Mock total count scalar
    mock_execute_result.scalar_one.return_value = 1
    # Mock results scalars returning matched article
    mock_session.execute.return_value = mock_execute_result

    # 1. Test search matching analysis summary_en
    mock_execute_result.scalars.return_value.all.return_value = [analyzed_article]
    response = client.get("/api/news?search=Specialized")
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == "analyzed-art-1"
    called_stmt_str = str(mock_session.execute.call_args_list[0][0][0]).lower()
    # verify that the query performed a join/outerjoin to analysis and filtered by summary_en
    assert "analysis_results" in called_stmt_str

    # 2. Test filter by urgency
    mock_session.execute.reset_mock()
    response = client.get("/api/news?urgency=high")
    assert response.status_code == 200
    called_stmt_str = str(mock_session.execute.call_args_list[0][0][0]).lower()
    assert "urgency" in called_stmt_str

    # 3. Test filter by is_analyzed=True
    mock_session.execute.reset_mock()
    response = client.get("/api/news?is_analyzed=true")
    assert response.status_code == 200
    called_stmt_str = str(mock_session.execute.call_args_list[0][0][0]).lower()
    assert "join analysis_results on news_articles.id = analysis_results.article_id" in called_stmt_str

    # 4. Test filter by is_analyzed=False
    mock_session.execute.reset_mock()
    response = client.get("/api/news?is_analyzed=false")
    assert response.status_code == 200
    called_stmt_str = str(mock_session.execute.call_args_list[0][0][0]).lower()
    assert "analysis_results.id is null" in called_stmt_str

