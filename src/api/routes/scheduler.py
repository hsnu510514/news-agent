from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timezone
from apscheduler.triggers.cron import CronTrigger

from src.storage.database import get_session
from src.models.schema import JobConfig, TaskRun
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
    volume_threshold: Optional[int] = None
    cooldown_minutes: int = 5
    in_cooldown: bool = False
    cooldown_remaining_seconds: int = 0

    class Config:
        from_attributes = True


class JobConfigUpdate(BaseModel):
    enabled: bool
    trigger_type: str
    schedule_value: str
    volume_threshold: Optional[int] = None
    cooldown_minutes: Optional[int] = 5

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


def _get_cooldown_details(config: JobConfig) -> tuple[bool, int]:
    if not config.last_run_time:
        return False, 0
    
    last_run = config.last_run_time
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)
        
    elapsed = datetime.now(timezone.utc) - last_run
    elapsed_sec = int(elapsed.total_seconds())
    cooldown_sec = (config.cooldown_minutes or 5) * 60
    
    if elapsed_sec < cooldown_sec:
        return True, max(0, cooldown_sec - elapsed_sec)
    return False, 0


@router.get("/jobs", response_model=List[JobConfigResponse])
async def get_jobs(session: AsyncSession = Depends(get_session)) -> List[JobConfigResponse]:
    result = await session.execute(select(JobConfig).order_by(JobConfig.id))
    configs = result.scalars().all()

    response = []
    for config in configs:
        job = scheduler.get_job(config.id)
        next_run = job.next_run_time if job else None
        in_cooldown, cooldown_rem = _get_cooldown_details(config)

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
                volume_threshold=config.volume_threshold,
                cooldown_minutes=config.cooldown_minutes,
                in_cooldown=in_cooldown,
                cooldown_remaining_seconds=cooldown_rem,
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

    import uuid
    task_run_id = str(uuid.uuid4())
    task_run = TaskRun(
        id=task_run_id,
        job_id=job_id,
        task_name=config.name,
        trigger_type="manual",
        status="running",
        start_time=datetime.now(timezone.utc),
    )
    session.add(task_run)
    await session.commit()

    background_tasks.add_task(run_job_wrapper, job_id, "manual", task_run_id)
    return {"status": "triggered", "job_id": job_id, "task_run_id": task_run_id}


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
    config.volume_threshold = payload.volume_threshold
    if payload.cooldown_minutes is not None:
        config.cooldown_minutes = payload.cooldown_minutes
    await session.commit()

    # Apply to running scheduler immediately
    reschedule_job_in_scheduler(config)

    # Get active next run time
    job = scheduler.get_job(config.id)
    next_run = job.next_run_time if job else None
    in_cooldown, cooldown_rem = _get_cooldown_details(config)

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
        volume_threshold=config.volume_threshold,
        cooldown_minutes=config.cooldown_minutes,
        in_cooldown=in_cooldown,
        cooldown_remaining_seconds=cooldown_rem,
    )
