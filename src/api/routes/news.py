from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import NewsArticle, LanguageEnum, SentimentEnum, UrgencyEnum, AnalysisResult
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_news(
    language: LanguageEnum | None = None,
    source_type: str | None = None,
    sentiment: SentimentEnum | None = None,
    urgency: UrgencyEnum | None = None,
    is_analyzed: bool | None = None,
    since: datetime | None = None,
    search: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(NewsArticle).options(selectinload(NewsArticle.analysis)).order_by(desc(NewsArticle.published_at))
    count_stmt = select(func.count()).select_from(NewsArticle)

    # Exclude syndicated content by default
    stmt = stmt.where(NewsArticle.duplicate_of_id.is_(None))
    count_stmt = count_stmt.where(NewsArticle.duplicate_of_id.is_(None))

    if language:
        stmt = stmt.where(NewsArticle.language == language)
        count_stmt = count_stmt.where(NewsArticle.language == language)
    if source_type:
        stmt = stmt.where(NewsArticle.source_type == source_type)
        count_stmt = count_stmt.where(NewsArticle.source_type == source_type)
    if sentiment:
        stmt = stmt.join(NewsArticle.analysis).where(AnalysisResult.sentiment == sentiment)
        count_stmt = count_stmt.join(NewsArticle.analysis).where(AnalysisResult.sentiment == sentiment)
    if urgency:
        stmt = stmt.join(NewsArticle.analysis).where(AnalysisResult.urgency == urgency)
        count_stmt = count_stmt.join(NewsArticle.analysis).where(AnalysisResult.urgency == urgency)
    if is_analyzed is not None:
        if is_analyzed:
            stmt = stmt.join(NewsArticle.analysis)
            count_stmt = count_stmt.join(NewsArticle.analysis)
        else:
            stmt = stmt.outerjoin(NewsArticle.analysis).where(AnalysisResult.id.is_(None))
            count_stmt = count_stmt.outerjoin(NewsArticle.analysis).where(AnalysisResult.id.is_(None))
    if since:
        stmt = stmt.where(NewsArticle.published_at >= since)
        count_stmt = count_stmt.where(NewsArticle.published_at >= since)
    if search:
        from sqlalchemy import or_, String, cast
        stmt = stmt.outerjoin(NewsArticle.analysis)
        count_stmt = count_stmt.outerjoin(NewsArticle.analysis)
        search_filter = or_(
            NewsArticle.title.ilike(f"%{search}%"),
            AnalysisResult.summary_en.ilike(f"%{search}%"),
            AnalysisResult.summary_zh.ilike(f"%{search}%"),
            AnalysisResult.impact_assessment.ilike(f"%{search}%"),
            cast(AnalysisResult.topics, String).ilike(f"%{search}%"),
            cast(AnalysisResult.companies_mentioned, String).ilike(f"%{search}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

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
                "analysis": {
                    "id": r.analysis[0].id,
                    "urgency": r.analysis[0].urgency.value if r.analysis[0].urgency else None,
                    "sentiment": r.analysis[0].sentiment.value if r.analysis[0].sentiment else None,
                    "sentiment_score": r.analysis[0].sentiment_score,
                    "topics": r.analysis[0].topics,
                    "companies_mentioned": r.analysis[0].companies_mentioned,
                    "summary_en": r.analysis[0].summary_en,
                    "summary_zh": r.analysis[0].summary_zh,
                    "impact_assessment": r.analysis[0].impact_assessment,
                    "llm_model": r.analysis[0].llm_model,
                    "analyzed_at": r.analysis[0].analyzed_at.isoformat(),
                } if r.analysis else None,
            }
            for r in rows
        ],
    }


@router.get("/syndicated")
async def list_syndicated_news(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(NewsArticle)
        .options(selectinload(NewsArticle.duplicate_of))
        .where(NewsArticle.duplicate_of_id.isnot(None))
        .order_by(desc(NewsArticle.published_at))
    )
    count_stmt = select(func.count()).select_from(NewsArticle).where(NewsArticle.duplicate_of_id.isnot(None))

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
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "fetched_at": r.fetched_at.isoformat(),
                "primary_source": {
                    "id": r.duplicate_of.id,
                    "title": r.duplicate_of.title,
                    "url": r.duplicate_of.url,
                    "source_name": r.duplicate_of.source_name,
                } if r.duplicate_of else None,
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