from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import Insight, Subject, InsightFact, UrgencyEnum
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_insights(
    tag: str | None = None,
    subject_id: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(Insight).options(
        selectinload(Insight.subject),
        selectinload(Insight.facts).selectinload(InsightFact.source_article)
    ).order_by(desc(Insight.last_updated_at))

    if tag:
        # Check if tag is inside JSONB array tags
        stmt = stmt.where(Insight.tags.contains([tag]))
    if subject_id:
        stmt = stmt.where(Insight.subject_id == subject_id)

    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "dimension_name": r.dimension_name,
                "summary_en": r.summary_en,
                "summary_zh": r.summary_zh,
                "urgency": r.urgency.value,
                "sentiment": r.sentiment.value,
                "tags": r.tags,
                "last_updated_at": r.last_updated_at.isoformat(),
                "subject": {
                    "id": r.subject.id,
                    "name": r.subject.name,
                    "type": r.subject.type.value,
                    "tags": r.subject.tags,
                },
                "facts": [
                    {
                        "id": f.id,
                        "bullet_text_en": f.bullet_text_en,
                        "bullet_text_zh": f.bullet_text_zh,
                        "created_at": f.created_at.isoformat(),
                        "source_article": {
                            "id": f.source_article.id,
                            "title": f.source_article.title,
                            "title_zh": f.source_article.title_zh,
                            "url": f.source_article.url,
                            "source_name": f.source_article.source_name,
                        } if f.source_article else None,
                    }
                    for f in sorted(r.facts, key=lambda x: x.created_at, reverse=True)
                ],
            }
            for r in rows
        ]
    }


@router.get("/alerts")
async def list_emergency_alerts(
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Alerts are Insights where urgency is 'flash'
    stmt = select(Insight).options(
        selectinload(Insight.subject),
        selectinload(Insight.facts).selectinload(InsightFact.source_article)
    ).where(Insight.urgency == UrgencyEnum.FLASH).order_by(desc(Insight.last_updated_at))

    rows = (await session.execute(stmt)).scalars().all()

    return {
        "alerts": [
            {
                "id": r.id,
                "subject_name": r.subject.name,
                "dimension_name": r.dimension_name,
                "summary_en": r.summary_en,
                "summary_zh": r.summary_zh,
                "last_updated_at": r.last_updated_at.isoformat(),
                "recent_fact": r.facts[0].bullet_text_en if r.facts else None,
                "recent_fact_zh": r.facts[0].bullet_text_zh if r.facts else None,
            }
            for r in rows
        ]
    }
