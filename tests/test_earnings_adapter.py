import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.earnings_fetcher import EarningsIngestAdapter
from src.models.schema import EarningsReport, SourceTypeEnum

@pytest.mark.asyncio
async def test_earnings_adapter_fetch() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "trailingEps": 5.4,
        "totalRevenue": 100000000.0,
        "netIncomeToCommon": 20000000.0,
        "longName": "Test Corporation",
        "marketCap": 500000000,
    }
    
    mock_client = MagicMock(spec=httpx.AsyncClient)
    adapter = EarningsIngestAdapter()
    
    with (
        patch("yfinance.Ticker", return_value=mock_ticker),
        patch("src.ingest.earnings_fetcher.TRACKED_TICKERS", ["TEST"]),
    ):
        # Act
        articles = await adapter.fetch(mock_client, mock_session)
        
        # Assert
        assert len(articles) == 1
        rep = articles[0]
        assert isinstance(rep, EarningsReport)
        assert rep.ticker == "TEST"
        assert rep.company_name == "Test Corporation"
        assert rep.eps == 5.4
        assert rep.revenue == 100000000.0
        assert rep.net_income == 20000000.0


@pytest.mark.asyncio
async def test_earnings_adapter_filter_duplicates() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    existing_report = EarningsReport(ticker="TEST", revenue=100.0, eps=5.0)
    mock_result.scalar_one_or_none.return_value = existing_report
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    adapter = EarningsIngestAdapter()
    
    items = [
        # Duplicate: same revenue and eps
        EarningsReport(ticker="TEST", revenue=100.0, eps=5.0),
        # New: different revenue
        EarningsReport(ticker="TEST", revenue=120.0, eps=5.0),
    ]
    
    # Act
    filtered = await adapter.filter_duplicates(items, mock_session)
    
    # Assert
    assert len(filtered) == 1
    assert filtered[0].revenue == 120.0
