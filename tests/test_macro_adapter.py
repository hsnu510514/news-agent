import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import httpx
import pandas as pd
import sys
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingest.macro_fetcher import MacroIngestAdapter
from src.models.schema import MacroIndicator, SourceTypeEnum

@pytest.mark.asyncio
async def test_macro_adapter_fetch() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_client = MagicMock(spec=httpx.AsyncClient)
    
    # Mock FRED series
    pmi_series = pd.Series([50.1, 51.3], index=[pd.Timestamp("2026-04-01"), pd.Timestamp("2026-05-01")])
    mock_fred_instance = MagicMock()
    mock_fred_instance.get_series_latest_release.return_value = pmi_series
    mock_fred_class = MagicMock(return_value=mock_fred_instance)
    
    # Mock AKShare GDP
    gdp_df = pd.DataFrame([
        {"日期": "2026-04-01", "今值": "5.0"},
        {"日期": "2026-05-01", "今值": "5.2"}
    ])
    mock_akshare = MagicMock()
    mock_akshare.macro_china_gdp.return_value = gdp_df
    # Mock other fetchers to return None or empty so they don't crash
    mock_akshare.macro_china_cpi_yearly.return_value = None
    mock_akshare.macro_china_ppi_yearly.return_value = None
    mock_akshare.macro_china_pmi.return_value = None
    mock_akshare.macro_china_money_supply.return_value = None
    mock_akshare.macro_china_lpr.return_value = None
    
    sys.modules["fredapi"] = MagicMock()
    sys.modules["fredapi"].Fred = mock_fred_class
    sys.modules["akshare"] = mock_akshare
    
    adapter = MacroIngestAdapter()
    
    # Mock settings
    mock_indicators = {
        "US": [{"code": "PMI", "name": "US PMI", "fred_id": "ISM/MAN_PMI"}],
        "CN": [{"code": "GDP_CN", "name": "CN GDP", "source": "akshare"}]
    }
    
    with (
        patch("src.ingest.macro_fetcher.settings") as mock_settings,
        patch("src.ingest.macro_fetcher.MACRO_INDICATORS", mock_indicators),
    ):
        mock_settings.FRED_API_KEY = "test_key"
        
        # Act
        articles = await adapter.fetch(mock_client, mock_session)
        
        # Assert
        assert len(articles) == 2
        pmi = [a for a in articles if a.indicator_code == "PMI"][0]
        assert pmi.value == 51.3
        assert pmi.period == "2026-05"
        assert pmi.country == "US"
        
        gdp = [a for a in articles if a.indicator_code == "GDP_CN"][0]
        assert gdp.value == 5.2
        assert gdp.period == "2026-05"
        assert gdp.country == "CN"

    # Cleanup sys.modules
    del sys.modules["fredapi"]
    del sys.modules["akshare"]


@pytest.mark.asyncio
async def test_macro_adapter_filter_duplicates() -> None:
    # Arrange
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [("PMI", "2026-05")]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    adapter = MacroIngestAdapter()
    
    items = [
        # Duplicate: same code and period
        MacroIndicator(indicator_code="PMI", period="2026-05"),
        # New: different period
        MacroIndicator(indicator_code="PMI", period="2026-06"),
    ]
    
    # Act
    filtered = await adapter.filter_duplicates(items, mock_session)
    
    # Assert
    assert len(filtered) == 1
    assert filtered[0].period == "2026-06"
