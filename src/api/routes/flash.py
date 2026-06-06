from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import FlashNews, LanguageEnum
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_flash(
    language: LanguageEnum | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(FlashNews).order_by(desc(FlashNews.published_at))
    count_stmt = select(func.count()).select_from(FlashNews)

    if language:
        stmt = stmt.where(FlashNews.language == language)
        count_stmt = count_stmt.where(FlashNews.language == language)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "content": r.content,
                "language": r.language.value,
                "importance": r.importance,
                "related_symbols": r.related_symbols,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "source_type": r.source_type.value,
            }
            for r in rows
        ],
    }