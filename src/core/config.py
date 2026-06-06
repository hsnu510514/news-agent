from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    DATABASE_URL: str = "postgresql+asyncpg://newsagent:newsagent@localhost:5432/newsagent"

    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    NEWSAPI_KEY: str = ""
    FRED_API_KEY: str = ""

    FUTU_HOST: str = "127.0.0.1"
    FUTU_PORT: int = 33333

    QDRANT_URL: str = "http://localhost:6333"

    LOG_LEVEL: str = "INFO"
    SCHEDULER_ENABLED: bool = True

    LLM_CLASSIFY_MODEL: str = "gemini/gemini-2.0-flash"
    LLM_SUMMARIZE_MODEL: str = "gemini/gemini-2.0-flash"
    LLM_ANALYSIS_MODEL: str = "gemini/gemini-2.5-pro"
    LLM_EMBED_MODEL: str = "gemini/text-embedding-004"

    NEWS_FETCH_INTERVAL_MINUTES: int = 30
    NEWSAPI_FETCH_INTERVAL_MINUTES: int = 60
    EARNINGS_FETCH_INTERVAL_HOURS: int = 6
    MACRO_FETCH_INTERVAL_HOURS: int = 24


settings = Settings()