from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.ingest.sources import TRACKED_TICKERS
from src.models.schema import EarningsReport, SourceTypeEnum
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


from src.ingest.interface import BaseIngestAdapter, IngestionSourceType

class EarningsIngestAdapter(BaseIngestAdapter):
    async def fetch(self, client: httpx.AsyncClient, session: AsyncSession) -> Sequence[EarningsReport]:
        import yfinance as yf
        
        articles = []
        for ticker_symbol in TRACKED_TICKERS:
            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info
                if not info:
                    continue

                eps = info.get("trailingEps")
                revenue = info.get("totalRevenue")
                net_income = info.get("netIncomeToCommon")
                company_name = info.get("longName") or info.get("shortName", ticker_symbol)

                report = EarningsReport(
                    ticker=ticker_symbol,
                    company_name=company_name,
                    source_type=SourceTypeEnum.YFINANCE,
                    revenue=float(revenue) if revenue else None,
                    net_income=float(net_income) if net_income else None,
                    eps=float(eps) if eps else None,
                    report_date=datetime.now(tz=timezone.utc),
                    raw_data={
                        "market_cap": info.get("marketCap"),
                        "pe_ratio": info.get("trailingPE"),
                        "forward_pe": info.get("forwardPE"),
                        "dividend_yield": info.get("dividendYield"),
                        "beta": info.get("beta"),
                        "52week_high": info.get("fiftyTwoWeekHigh"),
                        "52week_low": info.get("fiftyTwoWeekLow"),
                        "volume": info.get("volume"),
                        "avg_volume": info.get("averageVolume"),
                    },
                )
                articles.append(report)
            except Exception:
                logger.exception("Failed to fetch yfinance data for %s", ticker_symbol)
        
        return articles

    async def filter_duplicates(self, items: Sequence[EarningsReport], session: AsyncSession) -> Sequence[EarningsReport]:
        if not items:
            return []

        # Deduplicate list itself by ticker
        unique_fetched = {}
        for item in items:
            unique_fetched[item.ticker] = item

        non_duplicates = []
        for ticker, item in unique_fetched.items():
            existing = await session.execute(
                select(EarningsReport)
                .where(
                    EarningsReport.ticker == ticker,
                    EarningsReport.source_type == SourceTypeEnum.YFINANCE,
                )
                .order_by(EarningsReport.report_date.desc())
            )
            latest = existing.scalars().first()
            if latest and latest.revenue == item.revenue and latest.eps == item.eps:
                continue
            non_duplicates.append(item)

        return non_duplicates


# Register the adapter
from src.ingest.pipeline import register_adapter
register_adapter(IngestionSourceType.EARNINGS, EarningsIngestAdapter())


# Deprecated shim wrapper
async def ingest_yfinance_earnings() -> int:
    """Deprecated: use src.ingest.pipeline.ingest_source instead."""
    from src.ingest.pipeline import ingest_source
    summary = await ingest_source(IngestionSourceType.EARNINGS)
    return summary.saved_count



async def ingest_yfinance_earnings_history() -> int:
    import yfinance as yf

    total_saved = 0
    async with async_session_factory() as session:
        for ticker_symbol in TRACKED_TICKERS:
            try:
                ticker = yf.Ticker(ticker_symbol)
                earnings = ticker.earnings
                if earnings is None or earnings.empty:
                    continue

                for idx, row in earnings.iterrows():
                    year = int(idx) if not isinstance(idx, str) else int(str(idx))
                    if isinstance(idx, str):
                        fiscal_year = int(idx)
                    else:
                        fiscal_year = year

                    existing = await session.execute(
                        select(EarningsReport).where(
                            EarningsReport.ticker == ticker_symbol,
                            EarningsReport.fiscal_year == fiscal_year,
                            EarningsReport.source_type == SourceTypeEnum.YFINANCE,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    report = EarningsReport(
                        ticker=ticker_symbol,
                        source_type=SourceTypeEnum.YFINANCE,
                        fiscal_year=fiscal_year,
                        period="annual",
                        revenue=float(row.get("Revenue", 0)),
                        net_income=float(row.get("Earnings", 0)),
                    )
                    session.add(report)
                    total_saved += 1
            except Exception:
                logger.exception("Failed to ingest yfinance earnings history for %s", ticker_symbol)

        await session.commit()

    return total_saved