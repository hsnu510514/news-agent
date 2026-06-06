from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import MacroIndicator
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_macro(
    country: str | None = None,
    indicator_code: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(MacroIndicator).order_by(desc(MacroIndicator.timestamp))
    count_stmt = select(func.count()).select_from(MacroIndicator)

    if country:
        stmt = stmt.where(MacroIndicator.country == country)
        count_stmt = count_stmt.where(MacroIndicator.country == country)
    if indicator_code:
        stmt = stmt.where(MacroIndicator.indicator_code == indicator_code)
        count_stmt = count_stmt.where(MacroIndicator.indicator_code == indicator_code)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "indicator_code": r.indicator_code,
                "indicator_name": r.indicator_name,
                "country": r.country,
                "value": r.value,
                "unit": r.unit,
                "period": r.period,
                "previous_value": r.previous_value,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ],
    }