from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    DATABASE_URL: str = "postgresql+asyncpg://newsagent:newsagent@localhost:5432/newsagent"

    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    NEWSAPI_KEY: str = ""
    FRED_API_KEY: str = ""

    RSSHUB_BASE_URL: str = "https://rsshub.app"
    RSSHUB_ACCESS_KEY: str = ""

    COLLECTOR_BASE_URL: str = "https://ho4s8ws8088wkss0c4c8cc0s.runrunstopstop.run"
    COLLECTOR_FETCH_INTERVAL_MINUTES: int = 30
    ENABLED_COLLECTOR_SOURCES: str = ""

    FUTU_HOST: str = "127.0.0.1"
    FUTU_PORT: int = 33333

    QDRANT_URL: str = "http://localhost:6333"

    LOG_LEVEL: str = "INFO"
    SCHEDULER_ENABLED: bool = True

    LLM_CLASSIFY_MODEL: str = ""
    LLM_SUMMARIZE_MODEL: str = ""
    LLM_ANALYSIS_MODEL: str = ""
    LLM_RELEVANCE_MODEL: str = ""
    LLM_EMBED_MODEL: str = ""
    LLM_EMBED_FALLBACK_MODEL: str = ""
    LLM_LIGHTWEIGHT_FALLBACK_MODEL: str = ""
    LLM_REASONING_FALLBACK_MODEL: str = ""
    DAILY_SPEND_LIMIT: float = 5.00
    LLM_PACING_DELAY: str = "auto"

    NEWS_FETCH_INTERVAL_MINUTES: int = 30
    NEWSAPI_FETCH_INTERVAL_MINUTES: int = 60
    EARNINGS_FETCH_INTERVAL_HOURS: int = 6
    MACRO_FETCH_INTERVAL_HOURS: int = 24
    NEWSAPI_DOMAINS: str = "bloomberg.com,reuters.com"
    ENABLED_RSS_FEEDS: str = "36Kr,Bloomberg,FT Markets"
    CUSTOM_RSS_FEEDS: str = "[]"
    DELETED_RSS_FEEDS: str = ""

    MAX_ANALYSIS_DURATION_MINUTES: int = 25
    ANALYSIS_BATCH_SIZE: int = 20


settings = Settings()

import os
import json

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "model_config.json")

def load_model_settings():
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                if hasattr(settings, key) and val is not None:
                    setattr(settings, key, val)
        except Exception as e:
            # Silence exception or print warning
            print(f"Warning: Failed to load dynamic model settings: {e}")

def save_model_settings(
    classify_model: str,
    summarize_model: str,
    analysis_model: str,
    relevance_model: str,
    embed_model: str,
    embed_fallback_model: str,
    lightweight_fallback_model: str,
    reasoning_fallback_model: str,
    daily_spend_limit: float,
    pacing_delay: str = "auto",
    newsapi_domains: str | None = None,
    enabled_rss_feeds: str | None = None,
    max_analysis_duration_minutes: int | None = None,
    analysis_batch_size: int | None = None,
    custom_rss_feeds: str | None = None,
    deleted_rss_feeds: str | None = None,
    enabled_collector_sources: str | None = None,
):
    if newsapi_domains is None:
        newsapi_domains = settings.NEWSAPI_DOMAINS
    if enabled_rss_feeds is None:
        enabled_rss_feeds = settings.ENABLED_RSS_FEEDS
    if max_analysis_duration_minutes is None:
        max_analysis_duration_minutes = settings.MAX_ANALYSIS_DURATION_MINUTES
    if analysis_batch_size is None:
        analysis_batch_size = settings.ANALYSIS_BATCH_SIZE
    if custom_rss_feeds is None:
        custom_rss_feeds = settings.CUSTOM_RSS_FEEDS
    if deleted_rss_feeds is None:
        deleted_rss_feeds = settings.DELETED_RSS_FEEDS
    if enabled_collector_sources is None:
        enabled_collector_sources = settings.ENABLED_COLLECTOR_SOURCES

    data = {
        "LLM_CLASSIFY_MODEL": classify_model,
        "LLM_SUMMARIZE_MODEL": summarize_model,
        "LLM_ANALYSIS_MODEL": analysis_model,
        "LLM_RELEVANCE_MODEL": relevance_model,
        "LLM_EMBED_MODEL": embed_model,
        "LLM_EMBED_FALLBACK_MODEL": embed_fallback_model,
        "LLM_LIGHTWEIGHT_FALLBACK_MODEL": lightweight_fallback_model,
        "LLM_REASONING_FALLBACK_MODEL": reasoning_fallback_model,
        "DAILY_SPEND_LIMIT": daily_spend_limit,
        "LLM_PACING_DELAY": pacing_delay,
        "NEWSAPI_DOMAINS": newsapi_domains,
        "ENABLED_RSS_FEEDS": enabled_rss_feeds,
        "MAX_ANALYSIS_DURATION_MINUTES": max_analysis_duration_minutes,
        "ANALYSIS_BATCH_SIZE": analysis_batch_size,
        "CUSTOM_RSS_FEEDS": custom_rss_feeds,
        "DELETED_RSS_FEEDS": deleted_rss_feeds,
        "ENABLED_COLLECTOR_SOURCES": enabled_collector_sources,
    }
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    for key, val in data.items():
        if val is not None:
            setattr(settings, key, val)