from src.api.routes import news, analysis, earnings, macro, market_wire, trigger, scheduler, insights, briefings, glossary, tasks

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.database import get_session

from src.core.llm import api_status_tracker
from src.storage.vectorstore import client, COLLECTION_NAME

app = FastAPI(
    title="News Agent API",
    description="AI-powered investment research agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(earnings.router, prefix="/api/earnings", tags=["Earnings"])
app.include_router(macro.router, prefix="/api/macro", tags=["Macro"])
app.include_router(market_wire.router, prefix="/api/market-wire", tags=["Market Wire"])
app.include_router(trigger.router, prefix="/api/trigger", tags=["Triggers"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["Scheduler"])
app.include_router(insights.router, prefix="/api/insights", tags=["Insights"])
app.include_router(briefings.router, prefix="/api/briefings", tags=["Daily Briefings"])
app.include_router(glossary.router, prefix="/api/glossary", tags=["Entity Glossary"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Task Executions"])



@app.get("/api/system/status", tags=["System Status"])
async def get_system_status(
    session: AsyncSession = Depends(get_session),
) -> dict:
    # 1. LLM API Status
    llm_api_report = {
        "status": api_status_tracker.status,
        "error_message": api_status_tracker.error_message,
        "requests_made_today": api_status_tracker.requests_made_today,
        "estimated_daily_limit": api_status_tracker.estimated_daily_limit,
    }

    # 2. Database Status
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        db_report = {"status": "healthy", "error_message": ""}
    except Exception as e:
        db_report = {"status": "error", "error_message": str(e)}

    # 3. Qdrant Status
    try:
        client.get_collection(COLLECTION_NAME)
        qdrant_report = {"status": "healthy", "error_message": ""}
    except Exception as e:
        qdrant_report = {"status": "error", "error_message": str(e)}

    return {
        "llm_api": llm_api_report,
        "database": db_report,
        "qdrant": qdrant_report,
    }


@app.get("/api/alerts", tags=["Emergency Alerts"])
async def get_alerts_endpoint(
    session: AsyncSession = Depends(get_session),
) -> dict:
    from src.api.routes.insights import list_emergency_alerts
    return await list_emergency_alerts(session)


@app.on_event("startup")
async def startup() -> None:
    from src.storage.database import init_db
    from src.storage.vectorstore import ensure_collection
    from src.scheduler.jobs import start_scheduler
    from src.core.llm import llm_queue

    await init_db()
    
    # Reset any task runs stuck in "running" status from previous session
    try:
        from src.models.schema import TaskRun
        from sqlalchemy import update
        from src.storage.database import async_session_factory
        from datetime import datetime, timezone
        async with async_session_factory() as session:
            await session.execute(
                update(TaskRun)
                .where(TaskRun.status == "running")
                .values(
                    status="failed",
                    end_time=datetime.now(timezone.utc),
                    message="Task interrupted due to server restart/crash."
                )
            )
            await session.commit()
    except Exception:
        import logging
        logging.getLogger("news-agent").exception("Failed to clean up stuck task runs on startup")

    ensure_collection()
    llm_queue.start()
    await start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    from src.storage.database import close_db
    from src.scheduler.jobs import stop_scheduler
    from src.core.llm import llm_queue

    stop_scheduler()
    await llm_queue.stop()
    await close_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}