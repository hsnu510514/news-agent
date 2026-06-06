from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import AnalysisResult, SentimentEnum, UrgencyEnum
from src.storage.database import get_session

router = APIRouter()


@router.get("")
async def list_analysis(
    sentiment: SentimentEnum | None = None,
    urgency: UrgencyEnum | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(AnalysisResult).order_by(desc(AnalysisResult.analyzed_at))
    count_stmt = select(func.count()).select_from(AnalysisResult)

    if sentiment:
        stmt = stmt.where(AnalysisResult.sentiment == sentiment)
        count_stmt = count_stmt.where(AnalysisResult.sentiment == sentiment)
    if urgency:
        stmt = stmt.where(AnalysisResult.urgency == urgency)
        count_stmt = count_stmt.where(AnalysisResult.urgency == urgency)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "article_id": r.article_id,
                "urgency": r.urgency.value if r.urgency else None,
                "sentiment": r.sentiment.value if r.sentiment else None,
                "sentiment_score": r.sentiment_score,
                "topics": r.topics,
                "entities": r.entities,
                "companies_mentioned": r.companies_mentioned,
                "summary_en": r.summary_en,
                "summary_zh": r.summary_zh,
                "impact_assessment": r.impact_assessment,
                "llm_model": r.llm_model,
                "analyzed_at": r.analyzed_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, le=50),
) -> dict:
    from src.core.llm import get_embedding
    from src.storage.vectorstore import search_embeddings

    query_vector = await get_embedding(q)
    results = search_embeddings(query_vector, limit=limit)
    return {"query": q, "results": results}