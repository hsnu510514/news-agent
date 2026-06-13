from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone

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


class TaskHistoryResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[TaskRunResponse]


@router.get("/history", response_model=TaskHistoryResponse)
async def get_task_history(
    job_id: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session)
) -> dict:
    # 1. Count total records
    count_stmt = select(func.count(TaskRun.id))
    if job_id:
        count_stmt = count_stmt.where(TaskRun.job_id == job_id)
    total = (await session.execute(count_stmt)).scalar_one()

    # 2. Get paginated items
    stmt = select(TaskRun)
    if job_id:
        stmt = stmt.where(TaskRun.job_id == job_id)
    stmt = stmt.order_by(TaskRun.start_time.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items
    }


class AnalysisStatsResponse(BaseModel):
    total_news: int
    pending_news: int
    pending_preprocessing: int
    pending_analysis: int
    active_run: Optional[TaskRunResponse] = None
    llm_api_status: Optional[dict] = None


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
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta
    from src.core.llm import api_status_tracker

    # 1. Total news count
    stmt_total = select(func.count(NewsArticle.id))
    total_news = (await session.execute(stmt_total)).scalar_one_or_none() or 0

    # 2. Pending pre-processing count (is_relevant is None)
    stmt_pending_pre = select(func.count(NewsArticle.id)).where(NewsArticle.is_relevant.is_(None))
    pending_preprocessing = (await session.execute(stmt_pending_pre)).scalar_one_or_none() or 0

    # 3. Pending AI analysis count (is_relevant is True, no AnalysisResult)
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    stmt_pending_analysis = (
        select(func.count(NewsArticle.id))
        .outerjoin(AnalysisResult, NewsArticle.id == AnalysisResult.article_id)
        .where(AnalysisResult.id.is_(None))
        .where(NewsArticle.is_relevant == True)
        .where(NewsArticle.content.isnot(None))
        .where(NewsArticle.published_at >= cutoff)
    )
    pending_analysis = (await session.execute(stmt_pending_analysis)).scalar_one_or_none() or 0

    # 4. Active run (any active running job)
    stmt_active = (
        select(TaskRun)
        .where(TaskRun.status == "running")
        .order_by(TaskRun.start_time.desc())
        .limit(1)
    )
    active_run = (await session.execute(stmt_active)).scalars().first()

    return {
        "total_news": total_news,
        "pending_news": pending_analysis,  # legacy fallback
        "pending_preprocessing": pending_preprocessing,
        "pending_analysis": pending_analysis,
        "active_run": active_run,
        "llm_api_status": {
            "status": api_status_tracker.status,
            "error_message": api_status_tracker.error_message,
            "requests_made_today": api_status_tracker.requests_made_today,
            "estimated_daily_limit": api_status_tracker.estimated_daily_limit,
        }
    }


@router.post("/{task_run_id}/stop")
async def stop_task_run(
    task_run_id: str,
    session: AsyncSession = Depends(get_session)
) -> dict:
    from fastapi import HTTPException

    stmt = select(TaskRun).where(TaskRun.id == task_run_id)
    task_run = (await session.execute(stmt)).scalar_one_or_none()
    if not task_run:
        raise HTTPException(status_code=404, detail="Task run not found")

    if task_run.status == "running":
        task_run.status = "failed"
        task_run.message = "Stopped by user"
        task_run.end_time = datetime.now(timezone.utc)
        await session.commit()

    return {"status": "stopped", "task_run_id": task_run_id}

