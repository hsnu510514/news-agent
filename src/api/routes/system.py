from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.core.llm import model_quota_tracker
from src.core.config import settings, save_model_settings

router = APIRouter()

# Schema for updating model allocations
class ModelAllocationPayload(BaseModel):
    LLM_CLASSIFY_MODEL: str
    LLM_SUMMARIZE_MODEL: str
    LLM_ANALYSIS_MODEL: str
    LLM_RELEVANCE_MODEL: str
    LLM_EMBED_MODEL: str
    LLM_EMBED_FALLBACK_MODEL: str
    LLM_LIGHTWEIGHT_FALLBACK_MODEL: str
    LLM_REASONING_FALLBACK_MODEL: str
    DAILY_SPEND_LIMIT: float
    LLM_PACING_DELAY: str = "auto"
    MAX_ANALYSIS_DURATION_MINUTES: int = 25
    ANALYSIS_BATCH_SIZE: int = 20
    NEWSAPI_DOMAINS: str
    ENABLED_RSS_FEEDS: str
    CUSTOM_RSS_FEEDS: str = "[]"
    DELETED_RSS_FEEDS: str = ""
    ENABLED_COLLECTOR_SOURCES: str = ""


# List of recommended models for options select list in frontend
AVAILABLE_MODELS = [
    "ollama/gemma4:12b",
    "ollama/nomic-embed-text"
]


@router.get("/models")
async def get_models():
    all_available = AVAILABLE_MODELS.copy()
    import httpx
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                for m in models:
                    name = m.get("name")
                    if name:
                        ollama_name = name if name.startswith("ollama/") else f"ollama/{name}"
                        if ollama_name not in all_available:
                            all_available.append(ollama_name)
    except Exception:
        pass

    return {
        "allocations": {
            "LLM_CLASSIFY_MODEL": settings.LLM_CLASSIFY_MODEL,
            "LLM_SUMMARIZE_MODEL": settings.LLM_SUMMARIZE_MODEL,
            "LLM_ANALYSIS_MODEL": settings.LLM_ANALYSIS_MODEL,
            "LLM_RELEVANCE_MODEL": settings.LLM_RELEVANCE_MODEL,
            "LLM_EMBED_MODEL": settings.LLM_EMBED_MODEL,
            "LLM_EMBED_FALLBACK_MODEL": settings.LLM_EMBED_FALLBACK_MODEL,
            "LLM_LIGHTWEIGHT_FALLBACK_MODEL": settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL,
            "LLM_REASONING_FALLBACK_MODEL": settings.LLM_REASONING_FALLBACK_MODEL,
            "DAILY_SPEND_LIMIT": settings.DAILY_SPEND_LIMIT,
            "LLM_PACING_DELAY": settings.LLM_PACING_DELAY,
            "MAX_ANALYSIS_DURATION_MINUTES": settings.MAX_ANALYSIS_DURATION_MINUTES,
            "ANALYSIS_BATCH_SIZE": settings.ANALYSIS_BATCH_SIZE,
            "NEWSAPI_DOMAINS": settings.NEWSAPI_DOMAINS,
            "ENABLED_RSS_FEEDS": settings.ENABLED_RSS_FEEDS,
            "CUSTOM_RSS_FEEDS": settings.CUSTOM_RSS_FEEDS,
            "DELETED_RSS_FEEDS": settings.DELETED_RSS_FEEDS,
            "ENABLED_COLLECTOR_SOURCES": settings.ENABLED_COLLECTOR_SOURCES,
        },
        "available_models": all_available,
        "keys": {
            "gemini": bool(settings.GEMINI_API_KEY),
            "openai": bool(settings.OPENAI_API_KEY),
            "anthropic": bool(settings.ANTHROPIC_API_KEY),
            "deepseek": bool(settings.DEEPSEEK_API_KEY),
        }
    }


@router.put("/models")
async def update_models(payload: ModelAllocationPayload):
    try:
        # Save spend limit to config as well
        settings.DAILY_SPEND_LIMIT = payload.DAILY_SPEND_LIMIT
        settings.MAX_ANALYSIS_DURATION_MINUTES = payload.MAX_ANALYSIS_DURATION_MINUTES
        settings.ANALYSIS_BATCH_SIZE = payload.ANALYSIS_BATCH_SIZE
        settings.NEWSAPI_DOMAINS = payload.NEWSAPI_DOMAINS
        settings.ENABLED_RSS_FEEDS = payload.ENABLED_RSS_FEEDS
        settings.CUSTOM_RSS_FEEDS = payload.CUSTOM_RSS_FEEDS
        settings.DELETED_RSS_FEEDS = payload.DELETED_RSS_FEEDS
        settings.ENABLED_COLLECTOR_SOURCES = payload.ENABLED_COLLECTOR_SOURCES
        save_model_settings(
            classify_model=payload.LLM_CLASSIFY_MODEL,
            summarize_model=payload.LLM_SUMMARIZE_MODEL,
            analysis_model=payload.LLM_ANALYSIS_MODEL,
            relevance_model=payload.LLM_RELEVANCE_MODEL,
            embed_model=payload.LLM_EMBED_MODEL,
            embed_fallback_model=payload.LLM_EMBED_FALLBACK_MODEL,
            lightweight_fallback_model=payload.LLM_LIGHTWEIGHT_FALLBACK_MODEL,
            reasoning_fallback_model=payload.LLM_REASONING_FALLBACK_MODEL,
            daily_spend_limit=payload.DAILY_SPEND_LIMIT,
            pacing_delay=payload.LLM_PACING_DELAY,
            newsapi_domains=payload.NEWSAPI_DOMAINS,
            enabled_rss_feeds=payload.ENABLED_RSS_FEEDS,
            max_analysis_duration_minutes=payload.MAX_ANALYSIS_DURATION_MINUTES,
            analysis_batch_size=payload.ANALYSIS_BATCH_SIZE,
            custom_rss_feeds=payload.CUSTOM_RSS_FEEDS,
            deleted_rss_feeds=payload.DELETED_RSS_FEEDS,
            enabled_collector_sources=payload.ENABLED_COLLECTOR_SOURCES,
        )
        return {"status": "success", "message": "Model allocations updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save allocations: {e}")

# Static default limits for known models
MODEL_LIMITS = {
    "gemini/gemini-2.0-flash": {"rpm": 15, "tpm": 1_000_000, "rpd": 1_500},
    "gemini/gemini-2.5-flash": {"rpm": 15, "tpm": 1_000_000, "rpd": 1_500},
    "gemini/gemini-3.5-flash": {"rpm": 15, "tpm": 1_000_000, "rpd": 1_500},
    "gemini/gemini-2.5-pro": {"rpm": 2, "tpm": 32_000, "rpd": 50},
    "gemini/gemini-3.1-flash-lite": {"rpm": 15, "tpm": 1_000_000, "rpd": 1_500},
    "gemini/gemini-embedding-2": {"rpm": 1500, "tpm": None, "rpd": None},
    "gemini/gemini-embedding-001": {"rpm": 1500, "tpm": None, "rpd": None},
    "gemini/gemma-4-31b-it": {"rpm": 15, "tpm": None, "rpd": 1_500},
    "gemini/gemma-4-26b-a4b-it": {"rpm": 15, "tpm": None, "rpd": 1_500},
}

@router.get("/quotas")
async def get_quotas():
    # Gather statistics for all models currently tracked
    results = {}
    
    # We always include the configured models from settings and active limits
    from src.core.config import settings
    configured_models = {
        settings.LLM_CLASSIFY_MODEL,
        settings.LLM_SUMMARIZE_MODEL,
        settings.LLM_ANALYSIS_MODEL,
        settings.LLM_RELEVANCE_MODEL,
        settings.LLM_EMBED_MODEL,
        settings.LLM_EMBED_FALLBACK_MODEL,
        settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL,
        settings.LLM_REASONING_FALLBACK_MODEL
    }
    
    # Include both configured models and any model that has logged requests in tracker
    all_models = configured_models.union(model_quota_tracker._requests.keys())
    
    for model in all_models:
        rpm = model_quota_tracker.get_rpm(model)
        tpm = model_quota_tracker.get_tpm(model)
        rpd = model_quota_tracker.get_rpd(model)
        cost = model_quota_tracker.get_cost(model)
        
        # If the model is not currently configured and has no active metrics or cost, skip it
        if model not in configured_models and rpm == 0 and tpm == 0 and rpd == 0 and cost == 0.0:
            continue
            
        limits = MODEL_LIMITS.get(model, {"rpm": None, "tpm": None, "rpd": None})
        results[model] = {
            "rpm": rpm,
            "tpm": tpm,
            "rpd": rpd,
            "cost": cost,
            "prompt_tokens": model_quota_tracker.get_prompt_tokens(model),
            "completion_tokens": model_quota_tracker.get_completion_tokens(model),
            "status": model_quota_tracker.get_status(model),
            "error_message": model_quota_tracker.get_error_message(model),
            "limits": limits
        }
        
    return results

@router.post("/quotas/reset")
async def reset_quotas():
    model_quota_tracker.reset_all()
    return {"status": "success", "message": "In-memory metrics reset successfully."}


# Static fallback NewsAPI sources when API key is missing or request fails
FALLBACK_NEWSAPI_SOURCES = [
    {
        "id": "bloomberg",
        "name": "Bloomberg",
        "description": "Bloomberg delivers business and financial news, data, analysis, and video.",
        "url": "https://www.bloomberg.com",
        "category": "business",
        "language": "en",
        "country": "us"
    },
    {
        "id": "reuters",
        "name": "Reuters",
        "description": "Reuters.com brings you the latest news from around the world.",
        "url": "https://www.reuters.com",
        "category": "general",
        "language": "en",
        "country": "us"
    },
    {
        "id": "the-wall-street-journal",
        "name": "The Wall Street Journal",
        "description": "WSJ online coverage of breaking news and current headlines from the US and around the world.",
        "url": "https://www.wsj.com",
        "category": "business",
        "language": "en",
        "country": "us"
    },
    {
        "id": "cnbc",
        "name": "CNBC",
        "description": "CNBC is the world leader in business news and real-time financial market coverage.",
        "url": "https://www.cnbc.com",
        "category": "business",
        "language": "en",
        "country": "us"
    },
    {
        "id": "financial-times",
        "name": "Financial Times",
        "description": "News, analysis and comment from the Financial Times, the worldʼs leading global business publication.",
        "url": "https://www.ft.com",
        "category": "business",
        "language": "en",
        "country": "gb"
    },
    {
        "id": "marketwatch",
        "name": "MarketWatch",
        "description": "MarketWatch provides the latest stock market news, financial information, and personal finance advice.",
        "url": "https://www.marketwatch.com",
        "category": "business",
        "language": "en",
        "country": "us"
    },
    {
        "id": "associated-press",
        "name": "Associated Press",
        "description": "The Associated Press delivers in-depth coverage on today's international, national, and local news.",
        "url": "https://apnews.com",
        "category": "general",
        "language": "en",
        "country": "us"
    },
    {
        "id": "bbc-news",
        "name": "BBC News",
        "description": "Use BBC News for up-to-the-minute news, breaking news, video, audio and feature stories.",
        "url": "https://www.bbc.co.uk",
        "category": "general",
        "language": "en",
        "country": "gb"
    },
    {
        "id": "business-insider",
        "name": "Business Insider",
        "description": "Business Insider is a fast-growing business site with deep financial, media, tech, and other industry verticals.",
        "url": "https://www.businessinsider.com",
        "category": "business",
        "language": "en",
        "country": "us"
    },
    {
        "id": "economist",
        "name": "The Economist",
        "description": "Authoritative global news and analysis. The Economist offers fair-minded fact-checking.",
        "url": "https://www.economist.com",
        "category": "business",
        "language": "en",
        "country": "gb"
    },
    {
        "id": "sina-finance",
        "name": "Sina Finance (新浪财经)",
        "description": "Sina Finance delivers 24/7 financial and market news, company updates, and stock data in Chinese.",
        "url": "https://finance.sina.com.cn",
        "category": "business",
        "language": "zh",
        "country": "cn"
    },
    {
        "id": "wallstreetcn",
        "name": "Wall Street CN (华尔街见闻)",
        "description": "Leading provider of global financial news, macro indicators, and analysis in Chinese.",
        "url": "https://wallstreetcn.com",
        "category": "business",
        "language": "zh",
        "country": "cn"
    },
    {
        "id": "yicai",
        "name": "Yicai (第一财经)",
        "description": "Yicai is a leading Chinese financial media outlet providing comprehensive financial reports.",
        "url": "https://www.yicai.com",
        "category": "business",
        "language": "zh",
        "country": "cn"
    },
    {
        "id": "caixin",
        "name": "Caixin (财新网)",
        "description": "Caixin provides high-quality investigative journalism and financial news in Chinese.",
        "url": "https://www.caixin.com",
        "category": "business",
        "language": "zh",
        "country": "cn"
    },
    {
        "id": "36kr",
        "name": "36Kr (36氪)",
        "description": "36Kr is a leading Chinese business and technology media platform.",
        "url": "https://36kr.com",
        "category": "technology",
        "language": "zh",
        "country": "cn"
    }
]

# Simple in-memory cache for NewsAPI sources
_sources_cache = None
_sources_cache_time = None

@router.get("/newsapi-sources")
async def get_newsapi_sources():
    global _sources_cache, _sources_cache_time
    from datetime import datetime, timedelta
    import httpx
    
    # Return cache if valid (10 minutes lifetime)
    if _sources_cache is not None and _sources_cache_time is not None:
        if datetime.now() - _sources_cache_time < timedelta(minutes=10):
            return {"sources": _sources_cache}

    if not settings.NEWSAPI_KEY:
        return {"sources": FALLBACK_NEWSAPI_SOURCES}

    try:
        url = "https://newsapi.org/v2/top-headlines/sources"
        params = {"apiKey": settings.NEWSAPI_KEY}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "ok" and "sources" in data:
                sources_list = data["sources"]
                # Cache successful response
                _sources_cache = sources_list
                _sources_cache_time = datetime.now()
                return {"sources": sources_list}
    except Exception:
        pass

    # Fallback if request fails
    return {"sources": FALLBACK_NEWSAPI_SOURCES}


@router.get("/collector-sources")
async def get_collector_sources():
    import httpx
    if not settings.COLLECTOR_BASE_URL:
        return {"sources": []}
    try:
        base_url = settings.COLLECTOR_BASE_URL.rstrip("/")
        url = f"{base_url}/api/sources"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        if settings.RSSHUB_ACCESS_KEY:
            headers["Authorization"] = f"Bearer {settings.RSSHUB_ACCESS_KEY}"
            
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {"sources": data.get("sources", [])}
    except Exception:
        pass
    return {"sources": []}

