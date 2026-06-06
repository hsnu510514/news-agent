from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.ingest.sources import MACRO_INDICATORS
from src.models.schema import MacroIndicator, SourceTypeEnum
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


async def ingest_fred() -> int:
    try:
        from fredapi import Fred
    except ImportError:
        logger.warning("fredapi not available, skipping FRED ingestion")
        return 0

    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY not set, skipping FRED ingestion")
        return 0

    fred = Fred(api_key=settings.FRED_API_KEY)
    total_saved = 0

    async with async_session_factory() as session:
        for indicator in MACRO_INDICATORS["US"]:
            if "fred_id" not in indicator:
                continue

            try:
                count = await _process_fred_indicator(session, fred, indicator)
                total_saved += count
            except Exception:
                logger.exception("Failed to ingest FRED indicator: %s", indicator["code"])

    return total_saved


async def _process_fred_indicator(session: AsyncSession, fred, indicator: dict) -> int:
    series = fred.get_series_latest_release(indicator["fred_id"])
    if series is None or series.empty:
        return 0

    latest_date = series.index[-1]
    latest_value = float(series.iloc[-1])
    previous_value = float(series.iloc[-2]) if len(series) > 1 else None

    period_str = latest_date.strftime("%Y-%m") if hasattr(latest_date, "strftime") else str(latest_date)

    existing = await session.execute(
        select(MacroIndicator).where(
            MacroIndicator.indicator_code == indicator["code"],
            MacroIndicator.period == period_str,
        )
    )
    if existing.scalar_one_or_none():
        return 0

    timestamp = latest_date.to_pydatetime() if hasattr(latest_date, "to_pydatetime") else datetime.now(tz=timezone.utc)

    macro = MacroIndicator(
        indicator_code=indicator["code"],
        indicator_name=indicator["name"],
        country="US",
        source_type=SourceTypeEnum.FRED,
        value=latest_value,
        unit=indicator.get("unit", ""),
        period=period_str,
        previous_value=previous_value,
        timestamp=timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc),
    )
    session.add(macro)
    await session.commit()
    return 1


async def ingest_akshare() -> int:
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare not available, skipping CN macro ingestion")
        return 0

    total_saved = 0

    async with async_session_factory() as session:
        cn_indicators = MACRO_INDICATORS.get("CN", [])

        for indicator in cn_indicators:
            if indicator.get("source") != "akshare":
                continue

            try:
                count = await _process_akshare_indicator(session, indicator)
                total_saved += count
            except Exception:
                logger.exception("Failed to ingest AKShare indicator: %s", indicator["code"])

    return total_saved


AKSHARE_FETCHERS = {
    "GDP_CN": lambda: __import__("akshare").macro_china_gdp(),
    "CPI_CN": lambda: __import__("akshare").macro_china_cpi_yearly(),
    "PPI_CN": lambda: __import__("akshare").macro_china_ppi_yearly(),
    "PMI_CN": lambda: __import__("akshare").macro_china_pmi(),
    "M2_CN": lambda: __import__("akshare").macro_china_money_supply(),
    "INTEREST_RATE_CN": lambda: __import__("akshare").macro_china_lpr(),
}


async def _process_akshare_indicator(session: AsyncSession, indicator: dict) -> int:
    import akshare as ak

    code = indicator["code"]
    fetcher = AKSHARE_FETCHERS.get(code)
    if not fetcher:
        return 0

    df = fetcher()
    if df is None or df.empty:
        return 0

    latest_row = df.iloc[-1]
    columns = df.columns.tolist()

    date_col = columns[0]
    value_col = columns[1]

    latest_date = latest_row[date_col]
    latest_value = float(latest_row[value_col])

    previous_value = None
    if len(df) > 1:
        try:
            previous_value = float(df.iloc[-2][value_col])
        except Exception:
            pass

    period_str = str(latest_date)[:7] if latest_date else ""

    existing = await session.execute(
        select(MacroIndicator).where(
            MacroIndicator.indicator_code == code,
            MacroIndicator.period == period_str,
        )
    )
    if existing.scalar_one_or_none():
        return 0

    macro = MacroIndicator(
        indicator_code=code,
        indicator_name=indicator["name"],
        country="CN",
        source_type=SourceTypeEnum.AKSHARE,
        value=latest_value,
        unit="",
        period=period_str,
        previous_value=previous_value,
        timestamp=datetime.now(tz=timezone.utc),
    )
    session.add(macro)
    await session.commit()
    return 1