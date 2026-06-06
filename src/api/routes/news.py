from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import NewsArticle, LanguageEnum, SentimentEnum
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_news(
    language: LanguageEnum | None = None,
    source_type: str | None = None,
    sentiment: SentimentEnum | None = None,
    since: datetime | None = None,
    search: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(NewsArticle).order_by(desc(NewsArticle.published_at))
    count_stmt = select(func.count()).select_from(NewsArticle)

    if language:
        stmt = stmt.where(NewsArticle.language == language)
        count_stmt = count_stmt.where(NewsArticle.language == language)
    if source_type:
        stmt = stmt.where(NewsArticle.source_type == source_type)
        count_stmt = count_stmt.where(NewsArticle.source_type == source_type)
    if sentiment:
        stmt = stmt.join(NewsArticle.analysis).where(NewsArticle.analysis.has(sentiment=sentiment))
    if since:
        stmt = stmt.where(NewsArticle.published_at >= since)
        count_stmt = count_stmt.where(NewsArticle.published_at >= since)
    if search:
        stmt = stmt.where(NewsArticle.title.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(NewsArticle.title.ilike(f"%{search}%"))

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "title_zh": r.title_zh,
                "url": r.url,
                "source_type": r.source_type.value,
                "source_name": r.source_name,
                "language": r.language.value,
                "summary": r.summary,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "fetched_at": r.fetched_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/{article_id}")
async def get_news(
    article_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = (await session.execute(select(NewsArticle).where(NewsArticle.id == article_id))).scalar_one_or_none()
    if not row:
        return {"error": "Not found"}
    return {
        "id": row.id,
        "title": row.title,
        "title_zh": row.title_zh,
        "url": row.url,
        "source_type": row.source_type.value,
        "source_name": row.source_name,
        "language": row.language.value,
        "content": row.content,
        "summary": row.summary,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "fetched_at": row.fetched_at.isoformat(),
        "extra": row.extra,
    }