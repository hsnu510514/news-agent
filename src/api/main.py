from src.api.routes import news, analysis, earnings, macro, flash, trigger, scheduler, insights, briefings, glossary

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
app.include_router(flash.router, prefix="/api/flash", tags=["Flash News"])
app.include_router(trigger.router, prefix="/api/trigger", tags=["Triggers"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["Scheduler"])
app.include_router(insights.router, prefix="/api/insights", tags=["Insights"])
app.include_router(briefings.router, prefix="/api/briefings", tags=["Daily Briefings"])
app.include_router(glossary.router, prefix="/api/glossary", tags=["Entity Glossary"])


@app.on_event("startup")
async def startup() -> None:
    from src.storage.database import init_db
    from src.storage.vectorstore import ensure_collection
    from src.scheduler.jobs import start_scheduler

    await init_db()
    ensure_collection()
    await start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    from src.storage.database import close_db
    from src.scheduler.jobs import stop_scheduler

    stop_scheduler()
    await close_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}