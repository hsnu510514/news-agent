from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from src.storage.database import get_session
from src.models.schema import TaskRun

router = APIRouter()


class TaskRunResponse(BaseModel):
    id: str
    job_id: str
    task_name: str
    trigger_type: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    processed_count: int
    failed_count: int
    total_count: int
    message: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/history", response_model=List[TaskRunResponse])
async def get_task_history(
    job_id: Optional[str] = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session)
) -> List[TaskRun]:
    stmt = select(TaskRun)
    if job_id:
        stmt = stmt.where(TaskRun.job_id == job_id)
    stmt = stmt.order_by(TaskRun.start_time.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


class AnalysisStatsResponse(BaseModel):
    total_news: int
    pending_news: int
    active_run: Optional[TaskRunResponse] = None
    last_failed_run: Optional[TaskRunResponse] = None


@router.get("/active", response_model=List[TaskRunResponse])
async def get_active_tasks(
    session: AsyncSession = Depends(get_session)
) -> List[TaskRun]:
    stmt = select(TaskRun).where(TaskRun.status == "running").order_by(TaskRun.start_time.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/analysis-stats", response_model=AnalysisStatsResponse)
async def get_analysis_stats(
    session: AsyncSession = Depends(get_session)
) -> dict:
    from src.models.schema import NewsArticle, AnalysisResult
    from sqlalchemy import func, and_
    from datetime import datetime, timezone, timedelta

    # 1. Total news count
    stmt_total = select(func.count(NewsArticle.id))
    total_news = (await session.execute(stmt_total)).scalar_one_or_none() or 0

    # 2. Pending news count
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    stmt_pending = (
        select(func.count(NewsArticle.id))
        .outerjoin(AnalysisResult, NewsArticle.id == AnalysisResult.article_id)
        .where(AnalysisResult.id.is_(None))
        .where(NewsArticle.is_relevant == True)
        .where(NewsArticle.content.isnot(None))
        .where(NewsArticle.published_at >= cutoff)
    )
    pending_news = (await session.execute(stmt_pending)).scalar_one_or_none() or 0

    # 3. Active analysis run
    stmt_active = (
        select(TaskRun)
        .where(and_(TaskRun.job_id == "analysis", TaskRun.status == "running"))
        .order_by(TaskRun.start_time.desc())
        .limit(1)
    )
    active_run = (await session.execute(stmt_active)).scalars().first()

    # 4. Last failed analysis run
    stmt_failed = (
        select(TaskRun)
        .where(and_(TaskRun.job_id == "analysis", TaskRun.status == "failed"))
        .order_by(TaskRun.start_time.desc())
        .limit(1)
    )
    last_failed_run = (await session.execute(stmt_failed)).scalars().first()

    return {
        "total_news": total_news,
        "pending_news": pending_news,
        "active_run": active_run,
        "last_failed_run": last_failed_run,
    }

