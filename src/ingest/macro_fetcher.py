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


from src.ingest.interface import BaseIngestAdapter, IngestionSourceType

class MacroIngestAdapter(BaseIngestAdapter):
    async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[MacroIndicator]:
        articles = []
        
        # 1. Fetch FRED indicators
        try:
            from fredapi import Fred
            has_fred = True
        except ImportError:
            logger.warning("fredapi not available, skipping FRED ingestion")
            has_fred = False

        if has_fred and settings.FRED_API_KEY:
            try:
                fred = Fred(api_key=settings.FRED_API_KEY)
                for indicator in MACRO_INDICATORS.get("US", []):
                    if "fred_id" not in indicator:
                        continue
                    try:
                        series = fred.get_series_latest_release(indicator["fred_id"])
                        if series is None or series.empty:
                            continue

                        latest_date = series.index[-1]
                        latest_value = float(series.iloc[-1])
                        previous_value = float(series.iloc[-2]) if len(series) > 1 else None

                        period_str = latest_date.strftime("%Y-%m") if hasattr(latest_date, "strftime") else str(latest_date)
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
                        articles.append(macro)
                    except Exception:
                        logger.exception("Failed to fetch FRED indicator: %s", indicator["code"])
            except Exception:
                logger.exception("Failed to initialize Fred client")

        # 2. Fetch AKShare indicators
        try:
            import akshare as ak
            has_ak = True
        except ImportError:
            logger.warning("akshare not available, skipping CN macro ingestion")
            has_ak = False

        if has_ak:
            for indicator in MACRO_INDICATORS.get("CN", []):
                if indicator.get("source") != "akshare":
                    continue
                try:
                    code = indicator["code"]
                    fetcher = AKSHARE_FETCHERS.get(code)
                    if not fetcher:
                        continue

                    df = fetcher()
                    if df is None or df.empty:
                        continue

                    latest_row = df.iloc[-1]
                    columns = df.columns.tolist()

                    if code in ["CPI_CN", "PPI_CN"]:
                        date_col = columns[1]
                        value_col = columns[2]
                    else:
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
                    articles.append(macro)
                except Exception:
                    logger.exception("Failed to fetch AKShare indicator: %s", indicator["code"])

        return articles

    async def filter_duplicates(self, items: Sequence[MacroIndicator], session: AsyncSession) -> Sequence[MacroIndicator]:
        from sqlalchemy import or_, and_
        if not items:
            return []

        # Deduplicate list itself by (indicator_code, period)
        unique_fetched = {}
        for item in items:
            key = (item.indicator_code, item.period)
            unique_fetched[key] = item

        clauses = [
            and_(MacroIndicator.indicator_code == code, MacroIndicator.period == period)
            for code, period in unique_fetched.keys()
        ]
        
        stmt = select(MacroIndicator.indicator_code, MacroIndicator.period).where(or_(*clauses))
        res = await session.execute(stmt)
        existing = {(row[0], row[1]) for row in res.all()}

        return [item for key, item in unique_fetched.items() if key not in existing]


AKSHARE_FETCHERS = {
    "GDP_CN": lambda: __import__("akshare").macro_china_gdp(),
    "CPI_CN": lambda: __import__("akshare").macro_china_cpi_yearly(),
    "PPI_CN": lambda: __import__("akshare").macro_china_ppi_yearly(),
    "PMI_CN": lambda: __import__("akshare").macro_china_pmi(),
    "M2_CN": lambda: __import__("akshare").macro_china_money_supply(),
    "INTEREST_RATE_CN": lambda: __import__("akshare").macro_china_lpr(),
}


# Register the adapter
from src.ingest.pipeline import register_adapter
register_adapter(IngestionSourceType.MACRO, MacroIngestAdapter())


# Deprecated shim wrappers
async def ingest_fred() -> int:
    """Deprecated: use src.ingest.pipeline.ingest_source instead."""
    from src.ingest.pipeline import ingest_source
    summary = await ingest_source(IngestionSourceType.MACRO)
    return summary.saved_count

async def ingest_akshare() -> int:
    """Deprecated: use src.ingest.pipeline.ingest_source instead."""
    from src.ingest.pipeline import ingest_source
    summary = await ingest_source(IngestionSourceType.MACRO)
    return summary.saved_count