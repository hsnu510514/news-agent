from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import EarningsReport
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_earnings(
    ticker: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(EarningsReport).order_by(desc(EarningsReport.report_date))
    count_stmt = select(func.count()).select_from(EarningsReport)

    if ticker:
        stmt = stmt.where(EarningsReport.ticker.ilike(f"%{ticker}%"))
        count_stmt = count_stmt.where(EarningsReport.ticker.ilike(f"%{ticker}%"))

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "ticker": r.ticker,
                "company_name": r.company_name,
                "period": r.period,
                "fiscal_year": r.fiscal_year,
                "revenue": r.revenue,
                "net_income": r.net_income,
                "eps": r.eps,
                "eps_estimate": r.eps_estimate,
                "revenue_estimate": r.revenue_estimate,
                "report_date": r.report_date.isoformat() if r.report_date else None,
            }
            for r in rows
        ],
    }