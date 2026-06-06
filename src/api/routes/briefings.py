from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import DailyBriefing
from src.storage.database import get_session

router = APIRouter()


@router.get("/latest")
async def get_latest_briefing(
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(DailyBriefing).order_by(desc(DailyBriefing.generated_at)).limit(1)
    briefing = (await session.execute(stmt)).scalar_one_or_none()

    if not briefing:
        raise HTTPException(status_code=404, detail="No briefings found")

    return {
        "id": briefing.id,
        "summary_en": briefing.summary_en,
        "summary_zh": briefing.summary_zh,
        "key_takeaways_en": briefing.key_takeaways_en,
        "key_takeaways_zh": briefing.key_takeaways_zh,
        "generated_at": briefing.generated_at.isoformat(),
    }


@router.get("")
async def list_briefings(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(DailyBriefing).order_by(desc(DailyBriefing.generated_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    return {
        "briefings": [
            {
                "id": r.id,
                "summary_en": r.summary_en,
                "summary_zh": r.summary_zh,
                "generated_at": r.generated_at.isoformat(),
            }
            for r in rows
        ]
    }
