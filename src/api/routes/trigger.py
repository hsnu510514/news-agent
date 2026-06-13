from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from src.ingest.news_fetcher import ingest_rss
from src.ingest.newsapi_fetcher import ingest_newsapi
from src.ingest.earnings_fetcher import ingest_yfinance_earnings
from src.ingest.macro_fetcher import ingest_fred, ingest_akshare

from src.analysis.classifier import run_analysis_pipeline
from src.analysis.briefing import generate_daily_briefing

router = APIRouter()


class TriggerResponse(BaseModel):
    job: str
    status: str
    message: str = ""


@router.post("/ingest/rss")
async def trigger_rss(background_tasks: BackgroundTasks) -> TriggerResponse:
    background_tasks.add_task(ingest_rss)
    return TriggerResponse(job="ingest_rss", status="started")


@router.post("/ingest/newsapi")
async def trigger_newsapi(background_tasks: BackgroundTasks) -> TriggerResponse:
    background_tasks.add_task(ingest_newsapi)
    return TriggerResponse(job="ingest_newsapi", status="started")





@router.post("/ingest/earnings")
async def trigger_earnings(background_tasks: BackgroundTasks) -> TriggerResponse:
    background_tasks.add_task(ingest_yfinance_earnings)
    return TriggerResponse(job="ingest_earnings", status="started")


@router.post("/ingest/macro")
async def trigger_macro(background_tasks: BackgroundTasks) -> TriggerResponse:
    background_tasks.add_task(ingest_fred)
    background_tasks.add_task(ingest_akshare)
    return TriggerResponse(job="ingest_macro", status="started")



@router.post("/preprocessing")
async def trigger_preprocessing(background_tasks: BackgroundTasks) -> TriggerResponse:
    from src.ingest.preprocessing import run_preprocessing_pipeline
    background_tasks.add_task(run_preprocessing_pipeline)
    return TriggerResponse(job="preprocessing", status="started")


@router.post("/analyze")
async def trigger_analyze(background_tasks: BackgroundTasks) -> TriggerResponse:
    background_tasks.add_task(run_analysis_pipeline)
    return TriggerResponse(job="analyze", status="started")


@router.post("/briefing")
async def trigger_briefing(background_tasks: BackgroundTasks) -> TriggerResponse:
    background_tasks.add_task(generate_daily_briefing)
    return TriggerResponse(job="briefing", status="started")