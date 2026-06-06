from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger

from src.storage.database import get_session
from src.models.schema import JobConfig
from src.scheduler.jobs import scheduler, run_job_wrapper, reschedule_job_in_scheduler

router = APIRouter()


class JobConfigResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    trigger_type: str
    schedule_value: str
    last_run_time: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_message: Optional[str] = None
    next_run_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobConfigUpdate(BaseModel):
    enabled: bool
    trigger_type: str
    schedule_value: str

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger_type(cls, v: str) -> str:
        if v not in ("interval", "cron"):
            raise ValueError("trigger_type must be either 'interval' or 'cron'")
        return v

    @field_validator("schedule_value")
    @classmethod
    def validate_schedule_value(cls, v: str, info) -> str:
        trigger_type = info.data.get("trigger_type")
        if trigger_type == "interval":
            try:
                val = int(v)
                if val <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("For interval trigger, schedule_value must be a positive integer representing minutes/hours")
        elif trigger_type == "cron":
            try:
                CronTrigger.from_crontab(v)
            except Exception as e:
                raise ValueError(f"Invalid cron expression: {e}")
        return v


@router.get("/jobs", response_model=List[JobConfigResponse])
async def get_jobs(session: AsyncSession = Depends(get_session)) -> List[JobConfigResponse]:
    result = await session.execute(select(JobConfig).order_by(JobConfig.id))
    configs = result.scalars().all()

    response = []
    for config in configs:
        job = scheduler.get_job(config.id)
        next_run = job.next_run_time if job else None

        response.append(
            JobConfigResponse(
                id=config.id,
                name=config.name,
                enabled=config.enabled,
                trigger_type=config.trigger_type,
                schedule_value=config.schedule_value,
                last_run_time=config.last_run_time,
                last_run_status=config.last_run_status,
                last_run_message=config.last_run_message,
                next_run_time=next_run,
            )
        )
    return response


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
) -> dict:
    result = await session.execute(select(JobConfig).where(JobConfig.id == job_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Job not found")

    background_tasks.add_task(run_job_wrapper, job_id)
    return {"status": "triggered", "job_id": job_id}


@router.put("/jobs/{job_id}/config", response_model=JobConfigResponse)
async def update_job_config(
    job_id: str,
    payload: JobConfigUpdate,
    session: AsyncSession = Depends(get_session)
) -> JobConfigResponse:
    result = await session.execute(select(JobConfig).where(JobConfig.id == job_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update in database
    config.enabled = payload.enabled
    config.trigger_type = payload.trigger_type
    config.schedule_value = payload.schedule_value
    await session.commit()

    # Apply to running scheduler immediately
    reschedule_job_in_scheduler(config)

    # Get active next run time
    job = scheduler.get_job(config.id)
    next_run = job.next_run_time if job else None

    return JobConfigResponse(
        id=config.id,
        name=config.name,
        enabled=config.enabled,
        trigger_type=config.trigger_type,
        schedule_value=config.schedule_value,
        last_run_time=config.last_run_time,
        last_run_status=config.last_run_status,
        last_run_message=config.last_run_message,
        next_run_time=next_run,
    )
