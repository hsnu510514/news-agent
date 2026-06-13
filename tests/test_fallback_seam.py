import pytest
from unittest.mock import AsyncMock
from src.core.llm import call_with_fallback

@pytest.mark.asyncio
async def test_call_with_fallback_happy_path():
    # Arrange
    primary_model = "gemini/gemini-2.0-flash"
    fallback_model = "gemini/gemini-1.5-flash"
    
    mock_call_fn = AsyncMock(return_value="success_result")
    
    # Act
    result = await call_with_fallback(
        primary_model=primary_model,
        fallback_model=fallback_model,
        call_fn=mock_call_fn
    )
    
    # Assert
    assert result == "success_result"
    mock_call_fn.assert_called_once_with(primary_model)

@pytest.mark.asyncio
async def test_call_with_fallback_transient_retry():
    # Arrange
    primary_model = "gemini/gemini-2.0-flash"
    fallback_model = "gemini/gemini-1.5-flash"
    
    calls = []
    async def mock_call_fn(model):
        calls.append(model)
        if len(calls) == 1:
            raise Exception("Transient rate limit 429")
        return "success_after_retry"

    # Act
    result = await call_with_fallback(
        primary_model=primary_model,
        fallback_model=fallback_model,
        call_fn=mock_call_fn,
        max_retries=2,
        backoff_factor=0.01  # small backoff for fast tests
    )
    
    # Assert
    assert result == "success_after_retry"
    assert calls == [primary_model, primary_model]

@pytest.mark.asyncio
async def test_call_with_fallback_persistent_failure_failover():
    # Arrange
    primary_model = "gemini/gemini-2.0-flash"
    fallback_model = "gemini/fallback-model"
    
    calls = []
    async def mock_call_fn(model):
        calls.append(model)
        if model == primary_model:
            raise Exception("Persistent transient error")
        return "fallback_success"

    # Act
    result = await call_with_fallback(
        primary_model=primary_model,
        fallback_model=fallback_model,
        call_fn=mock_call_fn,
        max_retries=1,
        backoff_factor=0.01
    )
    
    # Assert
    assert result == "fallback_success"
    # 2 calls to primary (1 primary + 1 retry) and 1 call to fallback
    assert calls == [primary_model, primary_model, fallback_model]

@pytest.mark.asyncio
async def test_call_with_fallback_immediate_fallback_on_quota():
    from src.core.llm import DailyQuotaExhaustedError
    # Arrange
    primary_model = "gemini/gemini-2.0-flash"
    fallback_model = "gemini/fallback-model"
    
    calls = []
    async def mock_call_fn(model):
        calls.append(model)
        if model == primary_model:
            raise DailyQuotaExhaustedError("Daily spend limit reached")
        return "fallback_success"

    # Act
    result = await call_with_fallback(
        primary_model=primary_model,
        fallback_model=fallback_model,
        call_fn=mock_call_fn,
        max_retries=3,
        backoff_factor=0.01
    )
    
    # Assert
    assert result == "fallback_success"
    # Verify primary model was tried exactly once (no retries) before immediate fallback
    assert calls == [primary_model, fallback_model]

@pytest.mark.asyncio
async def test_call_with_fallback_immediate_abort_on_bad_request():
    # Arrange
    primary_model = "gemini/gemini-2.0-flash"
    fallback_model = "gemini/fallback-model"
    
    class MockBadRequestError(Exception):
        status_code = 400
        
    calls = []
    async def mock_call_fn(model):
        calls.append(model)
        raise MockBadRequestError("Bad Request structure validation error")

    # Act & Assert
    with pytest.raises(MockBadRequestError):
        await call_with_fallback(
            primary_model=primary_model,
            fallback_model=fallback_model,
            call_fn=mock_call_fn,
            max_retries=3,
            backoff_factor=0.01
        )
        
    # Verify primary model was tried exactly once and immediately raised (no retries, no fallback)
    assert calls == [primary_model]

@pytest.mark.asyncio
async def test_call_with_fallback_both_fail():
    # Arrange
    primary_model = "gemini/gemini-2.0-flash"
    fallback_model = "gemini/fallback-model"
    
    calls = []
    async def mock_call_fn(model):
        calls.append(model)
        raise Exception(f"Error on {model}")

    # Act & Assert
    with pytest.raises(Exception, match="Error on gemini/fallback-model"):
        await call_with_fallback(
            primary_model=primary_model,
            fallback_model=fallback_model,
            call_fn=mock_call_fn,
            max_retries=1,
            backoff_factor=0.01
        )
        
    # Verify primary model was tried twice (1 primary + 1 retry) and fallback was tried twice (1 fallback + 1 retry)
    assert calls == [primary_model, primary_model, fallback_model, fallback_model]





