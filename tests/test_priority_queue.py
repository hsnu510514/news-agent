import asyncio
import pytest
from src.core.llm import LLMTaskQueue

@pytest.mark.asyncio
async def test_priority_queue_execution_and_ordering():
    # 1. Initialize queue without starting worker automatically
    queue = LLMTaskQueue()
    
    execution_order = []
    
    async def mock_task(task_name: str, delay: float = 0.0):
        await asyncio.sleep(delay)
        execution_order.append(task_name)
        return f"result_{task_name}"
    
    # 2. Submit low priority task first (Priority 2)
    fut_low = await queue.submit_task(priority=2, func=mock_task, task_name="low_priority")
    
    # 3. Submit high priority task second (Priority 0)
    fut_high = await queue.submit_task(priority=0, func=mock_task, task_name="high_priority")
    
    # Verify tasks are pending and worker has not run them yet
    assert len(execution_order) == 0
    
    # 4. Start the worker to process tasks
    queue.start()
    
    # 5. Wait for both futures to resolve
    res_high = await fut_high
    res_low = await fut_low
    
    await queue.stop()
    
    # 6. Assertions
    assert res_high == "result_high_priority"
    assert res_low == "result_low_priority"
    # High priority task should have executed before low priority task
    assert execution_order == ["high_priority", "low_priority"]


@pytest.mark.asyncio
async def test_priority_queue_pacing():
    queue = LLMTaskQueue()
    queue.pacing_delay = 0.1  # Set a short pacing delay for testing
    
    execution_times = []
    
    async def mock_task(task_name: str):
        execution_times.append(asyncio.get_running_loop().time())
        return f"result_{task_name}"
    
    # Submit 3 tasks
    fut1 = await queue.submit_task(priority=1, func=mock_task, task_name="t1")
    fut2 = await queue.submit_task(priority=1, func=mock_task, task_name="t2")
    fut3 = await queue.submit_task(priority=1, func=mock_task, task_name="t3")
    
    queue.start()
    
    await fut1
    await fut2
    await fut3
    
    await queue.stop()
    
    assert len(execution_times) == 3
    # Check that each successive task ran at least 0.1s after the previous one
    diff1 = execution_times[1] - execution_times[0]
    diff2 = execution_times[2] - execution_times[1]
    
    # Use 0.08s as threshold to account for tiny timing variance
    assert diff1 >= 0.08
    assert diff2 >= 0.08


@pytest.mark.asyncio
async def test_priority_queue_transient_retry():
    queue = LLMTaskQueue()
    queue.pacing_delay = 0.0
    queue.backoff_factor = 0.001  # Make backoff instant for tests
    
    call_count = 0
    
    async def mock_failing_task():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Rate limit exceeded (HTTP 429)")
        return "success_after_retries"
        
    fut = await queue.submit_task(priority=1, func=mock_failing_task)
    queue.start()
    
    res = await fut
    await queue.stop()
    
    assert res == "success_after_retries"
    # Should have run 3 times: 2 failures, 1 success
    assert call_count == 3


@pytest.mark.asyncio
async def test_priority_queue_daily_quota_abort():
    from src.core.llm import DailyQuotaExhaustedError
    queue = LLMTaskQueue()
    queue.pacing_delay = 0.0
    queue.backoff_factor = 0.001
    
    # Task 1 throws a permanent Daily Quota error
    async def mock_quota_error_task():
        raise Exception("Quota exceeded for metric: generativelanguage.googleapis.com/requests_per_day, limit: 1500")
        
    # Task 2 is a normal task that should be aborted
    t2_run = False
    async def mock_normal_task():
        nonlocal t2_run
        t2_run = True
        return "normal_success"
        
    fut1 = await queue.submit_task(priority=1, func=mock_quota_error_task)
    fut2 = await queue.submit_task(priority=1, func=mock_normal_task)
    
    queue.start()
    
    # Task 1 should raise DailyQuotaExhaustedError
    with pytest.raises(DailyQuotaExhaustedError):
        await fut1
        
    # Task 2 should also raise DailyQuotaExhaustedError because the queue was aborted
    with pytest.raises(DailyQuotaExhaustedError):
        await fut2
        
    await queue.stop()
    
    # Task 2 must never have executed
    assert t2_run is False
    # Status tracker should be rate_limited
    assert queue.status_tracker.status == "rate_limited"


@pytest.mark.asyncio
async def test_priority_queue_submit_when_stopped():
    from src.core.llm import DailyQuotaExhaustedError
    queue = LLMTaskQueue()
    queue._quota_exhausted = True  # Simulate daily quota exhaustion
    
    async def mock_task():
        return "success"
        
    with pytest.raises(DailyQuotaExhaustedError):
        fut = await queue.submit_task(priority=1, func=mock_task)
        await fut


@pytest.mark.asyncio
async def test_priority_queue_day_change_restart():
    from src.core.llm import DailyQuotaExhaustedError
    from datetime import date, timedelta
    queue = LLMTaskQueue()
    queue.pacing_delay = 0.0
    queue.backoff_factor = 0.001
    
    # Simulate yesterday's reset date and rate limited status
    queue.status_tracker.error_message = "Rate limit hit"
    queue.status_tracker.status = "rate_limited"
    queue.status_tracker._last_reset_date = date.today() - timedelta(days=1)
    
    async def mock_task():
        return "restarted_success"
        
    # submit_task should reset date and start the queue automatically
    fut = await queue.submit_task(priority=1, func=mock_task)
    assert queue._running is True
    assert queue.status_tracker.status == "healthy"
    assert queue.status_tracker._last_reset_date == date.today()
    
    res = await fut
    assert res == "restarted_success"
    await queue.stop()



