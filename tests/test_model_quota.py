import pytest
import time
from datetime import date
from src.core.llm import ModelQuotaTracker

def test_model_quota_tracker_basic():
    # 1. Arrange: Create tracker
    tracker = ModelQuotaTracker()
    model = "gemini/gemini-2.0-flash"
    
    # Verify default state
    assert tracker.get_rpm(model) == 0
    assert tracker.get_tpm(model) == 0
    assert tracker.get_rpd(model) == 0
    
    # 2. Act: Record a request
    tracker.record_request(model, token_count=100)
    
    # 3. Assert: Verification
    assert tracker.get_rpm(model) == 1
    assert tracker.get_tpm(model) == 100
    assert tracker.get_rpd(model) == 1

def test_model_quota_tracker_rolling_window():
    tracker = ModelQuotaTracker()
    model = "gemini/gemini-2.0-flash"
    
    # Record requests at different times
    now = time.time()
    
    # Mock record_request with specific timestamps for testing
    tracker.record_request(model, token_count=50, timestamp=now - 70) # Outside 60s window
    tracker.record_request(model, token_count=100, timestamp=now - 30) # Inside
    tracker.record_request(model, token_count=200, timestamp=now - 10) # Inside
    
    # Rolling counts should only see the last two
    assert tracker.get_rpm(model) == 2
    assert tracker.get_tpm(model) == 300
    # Day request counts (RPD) should see all three
    assert tracker.get_rpd(model) == 3

@pytest.mark.asyncio
async def test_tracked_acompletion_success():
    from unittest.mock import AsyncMock, patch
    from src.core.llm import tracked_acompletion, model_quota_tracker
    
    # Reset tracker first
    model_quota_tracker.reset_all()
    
    model = "gemini/gemini-2.0-flash"
    mock_response = AsyncMock()
    mock_response.usage.prompt_tokens = 40
    mock_response.usage.completion_tokens = 60
    
    with patch("src.core.llm.acompletion", new=AsyncMock(return_value=mock_response)) as mock_acomp:
        res = await tracked_acompletion(model=model, messages=[{"role": "user", "content": "hi"}])
        assert res == mock_response
        mock_acomp.assert_called_once_with(model=model, messages=[{"role": "user", "content": "hi"}])
        
        # Verify usage was tracked
        assert model_quota_tracker.get_rpm(model) == 1
        assert model_quota_tracker.get_tpm(model) == 100
        assert model_quota_tracker.get_rpd(model) == 1
        assert model_quota_tracker.get_status(model) == "healthy"

@pytest.mark.asyncio
async def test_tracked_aembedding_success():
    from unittest.mock import AsyncMock, patch
    from src.core.llm import tracked_aembedding, model_quota_tracker
    
    model_quota_tracker.reset_all()
    
    model = "gemini/gemini-embedding-2"
    mock_response = AsyncMock()
    mock_response.data = [{"embedding": [0.1] * 768}]
    # Note: litellm aembedding response usually has usage or we estimate tokens based on character count/input
    mock_response.usage.prompt_tokens = 12
    mock_response.usage.completion_tokens = 0
    
    with patch("src.core.llm.aembedding", new=AsyncMock(return_value=mock_response)) as mock_aembed:
        res = await tracked_aembedding(model=model, input=["hello"])
        assert res == mock_response
        mock_aembed.assert_called_once_with(model=model, input=["hello"])
        
        # Verify usage was tracked
        assert model_quota_tracker.get_rpm(model) == 1
        assert model_quota_tracker.get_tpm(model) == 12
        assert model_quota_tracker.get_status(model) == "healthy"

def test_get_quotas_endpoint():
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.core.llm import model_quota_tracker
    
    model_quota_tracker.reset_all()
    model = "gemini/gemini-2.0-flash"
    model_quota_tracker.record_request(model, token_count=150)
    
    client = TestClient(app)
    response = client.get("/api/system/quotas")
    assert response.status_code == 200
    data = response.json()
    
    # Check that the model we used is in the response and has correct usage
    assert model in data
    assert data[model]["rpm"] == 1
    assert data[model]["tpm"] == 150
    assert data[model]["rpd"] == 1
    assert data[model]["status"] == "healthy"
    
    # Also check that it returns limits for that model
    assert data[model]["limits"]["rpm"] == 15
    assert data[model]["limits"]["tpm"] == 1000000

def test_reset_quotas_endpoint():
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.core.llm import model_quota_tracker
    
    model_quota_tracker.reset_all()
    model = "gemini/gemini-2.0-flash"
    model_quota_tracker.record_request(model, token_count=150)
    
    client = TestClient(app)
    # Check current state first
    assert model_quota_tracker.get_rpm(model) == 1
    
    # Post to reset
    response = client.post("/api/system/quotas/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "In-memory metrics reset successfully."}
    
    # Verify tracker is empty now
    assert model_quota_tracker.get_rpm(model) == 0

def test_model_settings_persistence(tmp_path):
    import os
    import shutil
    from src.core.config import settings
    # We will import the new functions (this will fail initially)
    from src.core.config import load_model_settings, save_model_settings
    import src.core.config as config_module
    
    test_config_file = str(tmp_path / "test_model_config.json")
    
    # Patch the config file path to a temp file
    orig_path = getattr(config_module, "CONFIG_FILE_PATH", None)
    config_module.CONFIG_FILE_PATH = test_config_file
    
    try:
        # Original values
        orig_classify = settings.LLM_CLASSIFY_MODEL
        orig_summarize = settings.LLM_SUMMARIZE_MODEL
        
        # Save new overrides
        save_model_settings(
            classify_model="gemini/test-classify",
            summarize_model="gemini/test-summarize",
            analysis_model="gemini/test-analysis",
            relevance_model="gemini/test-relevance",
            embed_model="gemini/test-embed",
            embed_fallback_model="gemini/test-embed-fallback",
            lightweight_fallback_model="gemini/test-lightweight-fallback",
            reasoning_fallback_model="gemini/test-reasoning-fallback",
            daily_spend_limit=10.0,
            newsapi_domains="test-bloomberg.com,test-reuters.com",
            enabled_rss_feeds="test-feed-1,test-feed-2"
        )
        
        # Check that settings were patched in memory
        assert settings.LLM_CLASSIFY_MODEL == "gemini/test-classify"
        assert settings.LLM_SUMMARIZE_MODEL == "gemini/test-summarize"
        assert settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL == "gemini/test-lightweight-fallback"
        assert settings.LLM_REASONING_FALLBACK_MODEL == "gemini/test-reasoning-fallback"
        assert settings.DAILY_SPEND_LIMIT == 10.0
        assert settings.NEWSAPI_DOMAINS == "test-bloomberg.com,test-reuters.com"
        assert settings.ENABLED_RSS_FEEDS == "test-feed-1,test-feed-2"
        
        # Check that file was written
        assert os.path.exists(test_config_file)
        
        # Reset settings memory values
        settings.LLM_CLASSIFY_MODEL = "gemini/reset-val"
        
        # Load overrides back from file
        load_model_settings()
        assert settings.LLM_CLASSIFY_MODEL == "gemini/test-classify"
        
    finally:
        # Cleanup
        if orig_path is not None:
            config_module.CONFIG_FILE_PATH = orig_path
        # Restore settings
        settings.LLM_CLASSIFY_MODEL = orig_classify
        settings.LLM_SUMMARIZE_MODEL = orig_summarize

def test_model_settings_pacing_delay_persistence(tmp_path):
    import os
    from src.core.config import settings
    from src.core.config import load_model_settings, save_model_settings
    import src.core.config as config_module
    
    test_config_file = str(tmp_path / "test_model_pacing_config.json")
    orig_path = getattr(config_module, "CONFIG_FILE_PATH", None)
    config_module.CONFIG_FILE_PATH = test_config_file
    
    # Assert default exists and is "auto"
    assert hasattr(settings, "LLM_PACING_DELAY")
    assert settings.LLM_PACING_DELAY == "auto"
    
    try:
        orig_classify = settings.LLM_CLASSIFY_MODEL
        orig_summarize = settings.LLM_SUMMARIZE_MODEL
        orig_pacing = settings.LLM_PACING_DELAY
        
        # Save new overrides including pacing_delay
        save_model_settings(
            classify_model="gemini/test-classify",
            summarize_model="gemini/test-summarize",
            analysis_model="gemini/test-analysis",
            relevance_model="gemini/test-relevance",
            embed_model="gemini/test-embed",
            embed_fallback_model="gemini/test-embed-fallback",
            lightweight_fallback_model="gemini/test-lightweight-fallback",
            reasoning_fallback_model="gemini/test-reasoning-fallback",
            daily_spend_limit=10.0,
            pacing_delay="1.5"
        )
        
        # Check that settings were patched in memory
        assert settings.LLM_PACING_DELAY == "1.5"
        
        # Reset settings memory value
        settings.LLM_PACING_DELAY = "auto"
        
        # Load overrides back from file
        load_model_settings()
        assert settings.LLM_PACING_DELAY == "1.5"
        
    finally:
        # Cleanup
        if orig_path is not None:
            config_module.CONFIG_FILE_PATH = orig_path
        # Restore settings
        settings.LLM_CLASSIFY_MODEL = orig_classify
        settings.LLM_SUMMARIZE_MODEL = orig_summarize
        settings.LLM_PACING_DELAY = orig_pacing

def test_models_allocation_endpoints(tmp_path):
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.core.config import settings
    import src.core.config as config_module
    
    test_config_file = str(tmp_path / "test_model_config.json")
    orig_path = getattr(config_module, "CONFIG_FILE_PATH", None)
    config_module.CONFIG_FILE_PATH = test_config_file
    
    try:
        orig_classify = settings.LLM_CLASSIFY_MODEL
        orig_summarize = settings.LLM_SUMMARIZE_MODEL
        orig_analysis = settings.LLM_ANALYSIS_MODEL
        orig_relevance = settings.LLM_RELEVANCE_MODEL
        orig_embed = settings.LLM_EMBED_MODEL
        orig_embed_fallback = settings.LLM_EMBED_FALLBACK_MODEL
        orig_lightweight_fallback = settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL
        orig_reasoning_fallback = settings.LLM_REASONING_FALLBACK_MODEL
        orig_daily_spend_limit = settings.DAILY_SPEND_LIMIT
        orig_pacing = settings.LLM_PACING_DELAY
        
        client = TestClient(app)
        
        # 1. Test GET /api/system/models
        response = client.get("/api/system/models")
        assert response.status_code == 200
        data = response.json()
        
        # Check keys are present
        assert "allocations" in data
        assert "LLM_CLASSIFY_MODEL" in data["allocations"]
        assert "LLM_SUMMARIZE_MODEL" in data["allocations"]
        assert "LLM_LIGHTWEIGHT_FALLBACK_MODEL" in data["allocations"]
        assert "LLM_REASONING_FALLBACK_MODEL" in data["allocations"]
        assert "DAILY_SPEND_LIMIT" in data["allocations"]
        assert "LLM_PACING_DELAY" in data["allocations"]
        assert data["allocations"]["LLM_PACING_DELAY"] == "auto"
        assert "available_models" in data
        assert "ollama/gemma4:12b" in data["available_models"]
        
        # 2. Test PUT /api/system/models
        payload = {
            "LLM_CLASSIFY_MODEL": "gemini/new-classify",
            "LLM_SUMMARIZE_MODEL": "gemini/new-summarize",
            "LLM_ANALYSIS_MODEL": "gemini/new-analysis",
            "LLM_RELEVANCE_MODEL": "gemini/new-relevance",
            "LLM_EMBED_MODEL": "gemini/new-embed",
            "LLM_EMBED_FALLBACK_MODEL": "gemini/new-embed-fallback",
            "LLM_LIGHTWEIGHT_FALLBACK_MODEL": "gemini/new-lightweight-fallback",
            "LLM_REASONING_FALLBACK_MODEL": "gemini/new-reasoning-fallback",
            "DAILY_SPEND_LIMIT": 7.50,
            "LLM_PACING_DELAY": "2.5",
            "NEWSAPI_DOMAINS": "test-bloomberg.com,test-reuters.com",
            "ENABLED_RSS_FEEDS": "test-feed-1,test-feed-2"
        }
        
        response = client.put("/api/system/models", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "success", "message": "Model allocations updated successfully."}
        
        # Assert in-memory values were updated
        assert settings.LLM_CLASSIFY_MODEL == "gemini/new-classify"
        assert settings.LLM_SUMMARIZE_MODEL == "gemini/new-summarize"
        assert settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL == "gemini/new-lightweight-fallback"
        assert settings.LLM_REASONING_FALLBACK_MODEL == "gemini/new-reasoning-fallback"
        assert settings.DAILY_SPEND_LIMIT == 7.50
        assert settings.LLM_PACING_DELAY == "2.5"
        assert settings.NEWSAPI_DOMAINS == "test-bloomberg.com,test-reuters.com"
        assert settings.ENABLED_RSS_FEEDS == "test-feed-1,test-feed-2"
        
    finally:
        if orig_path is not None:
            config_module.CONFIG_FILE_PATH = orig_path
        settings.LLM_CLASSIFY_MODEL = orig_classify
        settings.LLM_SUMMARIZE_MODEL = orig_summarize
        settings.LLM_ANALYSIS_MODEL = orig_analysis
        settings.LLM_RELEVANCE_MODEL = orig_relevance
        settings.LLM_EMBED_MODEL = orig_embed
        settings.LLM_EMBED_FALLBACK_MODEL = orig_embed_fallback
        settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL = orig_lightweight_fallback
        settings.LLM_REASONING_FALLBACK_MODEL = orig_reasoning_fallback
        settings.DAILY_SPEND_LIMIT = orig_daily_spend_limit
        settings.LLM_PACING_DELAY = orig_pacing


def test_models_endpoint_keys_and_curated_list(monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.core.config import settings
    
    # 1. Patch Settings keys to check status dictionary logic
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "key-present")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "key-present")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")

    from unittest.mock import AsyncMock, patch
    import httpx
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.ConnectError("offline"))):
        client = TestClient(app)
        response = client.get("/api/system/models")
    assert response.status_code == 200
    data = response.json()
    
    # Verify exactly our two Ollama models are present in available models list
    assert data["available_models"] == ["ollama/gemma4:12b", "ollama/nomic-embed-text"]
    
    # Verify provider keys check status mapping is correct
    assert "keys" in data
    assert data["keys"]["gemini"] is True
    assert data["keys"]["openai"] is False
    assert data["keys"]["anthropic"] is True
    assert data["keys"]["deepseek"] is False


def test_models_endpoint_ollama_discovery_success(monkeypatch):
    import httpx
    from fastapi.testclient import TestClient
    from src.api.main import app
    from unittest.mock import AsyncMock, patch

    mock_resp = httpx.Response(
        status_code=200,
        json={"models": [{"name": "gemma2:9b"}, {"name": "ollama/llama3:8b"}]}
    )
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        client = TestClient(app)
        response = client.get("/api/system/models")
        assert response.status_code == 200
        data = response.json()
        assert "ollama/gemma2:9b" in data["available_models"]
        assert "ollama/llama3:8b" in data["available_models"]
        assert "ollama/gemma4:12b" in data["available_models"]


def test_models_endpoint_ollama_discovery_failure(monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.main import app
    from unittest.mock import AsyncMock, patch
    import httpx

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.ConnectError("Ollama offline"))):
        client = TestClient(app)
        response = client.get("/api/system/models")
        assert response.status_code == 200
        data = response.json()
        assert data["available_models"] == ["ollama/gemma4:12b", "ollama/nomic-embed-text"]


@pytest.mark.asyncio
async def test_classify_fallback(monkeypatch):
    from src.core.llm import _raw_classify
    from src.core.config import settings
    from unittest.mock import MagicMock
    
    # 1. Arrange: set settings
    monkeypatch.setattr(settings, "LLM_CLASSIFY_MODEL", "gemini/primary-classify")
    monkeypatch.setattr(settings, "LLM_REASONING_FALLBACK_MODEL", "gemini/fallback-classify")
    
    # Track calls to see what models were tried
    models_called = []
    
    async def mock_tracked_acompletion(model, messages, **kwargs):
        models_called.append(model)
        if model == "gemini/primary-classify":
            raise ValueError("Primary API failed or rate limited")
        elif model == "gemini/fallback-classify":
            mock_res = MagicMock()
            mock_res.choices = [MagicMock()]
            mock_res.choices[0].message.content = '{"category": "macro"}'
            return mock_res
        raise ValueError(f"Unknown model called: {model}")
        
    monkeypatch.setattr("src.core.llm.tracked_acompletion", mock_tracked_acompletion)
    
    # 2. Act
    res = await _raw_classify("some text")
    
    # 3. Assert
    assert res == '{"category": "macro"}'
    assert "gemini/primary-classify" in models_called
    assert "gemini/fallback-classify" in models_called


@pytest.mark.asyncio
async def test_check_relevance_fallback(monkeypatch):
    from src.core.llm import _raw_check_relevance
    from src.core.config import settings
    from unittest.mock import MagicMock
    
    monkeypatch.setattr(settings, "LLM_RELEVANCE_MODEL", "gemini/primary-relevance")
    monkeypatch.setattr(settings, "LLM_LIGHTWEIGHT_FALLBACK_MODEL", "gemini/fallback-relevance")
    
    models_called = []
    
    async def mock_tracked_acompletion(model, messages, **kwargs):
        models_called.append(model)
        if model == "gemini/primary-relevance":
            raise ValueError("Primary API failed")
        elif model == "gemini/fallback-relevance":
            mock_res = MagicMock()
            mock_res.choices = [MagicMock()]
            mock_res.choices[0].message.content = '{"relevant": true}'
            return mock_res
        raise ValueError(f"Unknown model called: {model}")
        
    monkeypatch.setattr("src.core.llm.tracked_acompletion", mock_tracked_acompletion)
    
    # 2. Act
    # _raw_check_relevance takes a prompt argument
    res = await _raw_check_relevance("some relevance prompt")
    
    # 3. Assert
    assert res == '{"relevant": true}'
    assert "gemini/primary-relevance" in models_called
    assert "gemini/fallback-relevance" in models_called


def test_cost_and_token_breakdown_tracking():
    from src.core.llm import ModelQuotaTracker
    
    tracker = ModelQuotaTracker()
    model = "openai/gpt-4o-mini"
    
    # Verify default state
    assert tracker.get_cost(model) == 0.0
    assert tracker.get_prompt_tokens(model) == 0
    assert tracker.get_completion_tokens(model) == 0
    
    # Record a request with cost and token breakdown
    tracker.record_request(model, token_count=100, cost=0.0015, prompt_tokens=40, completion_tokens=60)
    
    assert tracker.get_cost(model) == 0.0015
    assert tracker.get_prompt_tokens(model) == 40
    assert tracker.get_completion_tokens(model) == 60


@pytest.mark.asyncio
async def test_tracked_acompletion_cost_calculation():
    from unittest.mock import AsyncMock, patch
    from src.core.llm import tracked_acompletion, model_quota_tracker
    
    model_quota_tracker.reset_all()
    model = "openai/gpt-4o-mini"
    mock_response = AsyncMock()
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 100
    
    with patch("src.core.llm.acompletion", new=AsyncMock(return_value=mock_response)) as mock_acomp, \
         patch("src.core.llm.litellm.completion_cost", return_value=0.0025):
         
        res = await tracked_acompletion(model=model, messages=[{"role": "user", "content": "hi"}])
        assert res == mock_response
        
        assert model_quota_tracker.get_cost(model) == 0.0025
        assert model_quota_tracker.get_prompt_tokens(model) == 50
        assert model_quota_tracker.get_completion_tokens(model) == 100


@pytest.mark.asyncio
async def test_daily_spend_limit_blocking(monkeypatch):
    from src.core.llm import tracked_acompletion, model_quota_tracker, DailyQuotaExhaustedError
    from src.core.config import settings
    from unittest.mock import AsyncMock, patch
    
    # Reset tracker and configure budget
    model_quota_tracker.reset_all()
    monkeypatch.setattr(settings, "DAILY_SPEND_LIMIT", 0.05)
    
    # 1. Simulate we already spent 0.06 (exceeding 0.05 limit)
    model_quota_tracker.record_request("openai/gpt-4o", token_count=1000, cost=0.06)
    
    # 2. Attempt a paid API call -> should fail immediately with DailyQuotaExhaustedError
    mock_response = AsyncMock()
    with patch("src.core.llm.acompletion", new=AsyncMock(return_value=mock_response)):
        with pytest.raises(DailyQuotaExhaustedError) as exc_info:
            await tracked_acompletion(model="openai/gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])
        assert "Daily spend limit of $0.05 reached" in str(exc_info.value)
        
    # 3. Attempt a local Ollama call -> should succeed (Ollama is local and exempt from budget checks)
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    with patch("src.core.llm.acompletion", new=AsyncMock(return_value=mock_response)) as mock_acomp:
        res = await tracked_acompletion(model="ollama/gemma4:12b", messages=[{"role": "user", "content": "hi"}])
        assert res == mock_response


@pytest.mark.asyncio
async def test_tracked_completion_and_embedding_unconfigured_model():
    from src.core.llm import tracked_acompletion, tracked_aembedding
    
    with pytest.raises(ValueError) as exc_info:
        await tracked_acompletion(model="", messages=[{"role": "user", "content": "hi"}])
    assert "Model configuration is incomplete" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        await tracked_aembedding(model="", input=["hi"])
    assert "Model configuration is incomplete" in str(exc_info.value)




