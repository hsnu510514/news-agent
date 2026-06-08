from __future__ import annotations

import logging

import litellm
from litellm import acompletion, aembedding

from src.core.config import settings

import asyncio
from datetime import date
from typing import Callable, Any

logger = logging.getLogger("news-agent")

litellm.suppress_debug_info = True


class DailyQuotaExhaustedError(Exception):
    """Raised when the Gemini API daily/persistent rate limit is exhausted."""
    pass


class APIStatusTracker:
    def __init__(self):
        self.status = "healthy"
        self.error_message = ""
        self.requests_made_today = 0
        self.estimated_daily_limit = 1500
        self._last_reset_date = date.today()

    def record_success(self):
        if date.today() != self._last_reset_date:
            self.requests_made_today = 0
            self._last_reset_date = date.today()
        self.status = "healthy"
        self.error_message = ""
        self.requests_made_today += 1

    def record_failure(self, error_msg: str, is_rate_limit: bool):
        self.status = "rate_limited" if is_rate_limit else "error"
        self.error_message = error_msg


# Instantiate singletons
api_status_tracker = APIStatusTracker()


class LLMTaskQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._seq = 0
        self._worker_task = None
        self._running = False
        self.pacing_delay = 4.0
        self.backoff_factor = 2.0
        self.status_tracker = api_status_tracker

    async def submit_task(self, priority: int, func: Callable, *args, **kwargs) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._seq += 1
        await self._queue.put((priority, self._seq, future, func, args, kwargs))
        return future

    def start(self):
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        # Clean up any remaining tasks in the queue if stopped
        await self._abort_all_pending_tasks(asyncio.CancelledError("Queue stopped"))

    async def _abort_all_pending_tasks(self, exception: Exception):
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                priority, seq, future, func, args, kwargs = item
                if not future.done():
                    future.set_exception(exception)
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def _worker_loop(self):
        while self._running:
            try:
                # Wait for a task
                item = await self._queue.get()
                priority, seq, future, func, args, kwargs = item
                
                if future.cancelled():
                    self._queue.task_done()
                    continue
                
                success = False
                attempts = 0
                max_retries = 3
                
                while not success and attempts <= max_retries:
                    try:
                        result = await func(*args, **kwargs)
                        self.status_tracker.record_success()
                        future.set_result(result)
                        success = True
                    except Exception as e:
                        error_msg = str(e)
                        is_rate_limit = "429" in error_msg or "rate limit" in error_msg.lower() or "quota" in error_msg.lower()
                        
                        # Check if it's a hard/permanent daily quota limit
                        is_permanent_quota = "quota exceeded" in error_msg.lower() and (
                            "daily" in error_msg.lower() 
                            or "limit: 0" in error_msg.lower() 
                            or "requests_per_day" in error_msg.lower()
                            or "requests per day" in error_msg.lower()
                            or "per_day" in error_msg.lower()
                            or "perday" in error_msg.lower()
                        )
                        
                        if is_permanent_quota:
                            self.status_tracker.record_failure(error_msg, is_rate_limit)
                            future.set_exception(DailyQuotaExhaustedError(error_msg))
                            # Fail all other pending tasks in the queue
                            await self._abort_all_pending_tasks(DailyQuotaExhaustedError(error_msg))
                            self._running = False
                            break
                        
                        if is_rate_limit and attempts < max_retries:
                            attempts += 1
                            sleep_duration = self.backoff_factor * (2 ** (attempts - 1))
                            logger.warning(
                                "Transient rate limit hit. Retrying task (attempt %d/%d) in %.2fs. Error: %s",
                                attempts, max_retries, sleep_duration, error_msg
                            )
                            await asyncio.sleep(sleep_duration)
                        else:
                            self.status_tracker.record_failure(error_msg, is_rate_limit)
                            future.set_exception(e)
                            break
                
                self._queue.task_done()
                
                # Apply pacing delay
                if self.pacing_delay > 0 and self._running:
                    await asyncio.sleep(self.pacing_delay)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Queue worker encountered an unexpected error")
                await asyncio.sleep(1)


# Instantiate singletons
llm_queue = LLMTaskQueue()


# Raw LLM completion functions wrapped for the queue
async def _raw_classify(text: str) -> str:
    response = await acompletion(
        model=settings.LLM_CLASSIFY_MODEL,
        messages=[{"role": "user", "content": f"{text}\n\nReturn your response as a valid JSON object only. Do not include any text outside the JSON."}],
        temperature=0.1,
    )
    return response.choices[0].message.content


async def classify(text: str, priority: int = 2) -> str:
    fut = await llm_queue.submit_task(priority, _raw_classify, text)
    return await fut


async def _raw_check_relevance(prompt: str) -> str:
    response = await acompletion(
        model=settings.LLM_RELEVANCE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content


async def check_relevance(title: str, summary: str, priority: int = 1) -> bool:
    import json
    prompt = (
        "You are an investment research filter. Analyze the news article title and summary.\n"
        "Determine if it is relevant to:\n"
        "1. Financial News (corporate earnings, stock market, company updates, sector trends, IPOs, mergers).\n"
        "2. Global Affairs & Macro Policy (geopolitics, trade, monetary/fiscal policy, regulations, central banks, elections).\n\n"
        "Return a JSON object with a single boolean field \"relevant\". Do not include any other text.\n\n"
        f"Title: {title}\n"
        f"Summary: {summary or ''}"
    )
    try:
        fut = await llm_queue.submit_task(priority, _raw_check_relevance, prompt)
        raw_response = await fut
        clean_response = raw_response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.startswith("```"):
            clean_response = clean_response[3:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()
        data = json.loads(clean_response)
        return bool(data.get("relevant", True))
    except Exception as e:
        logger.warning(f"Error checking relevance for title '{title}': {e}")
        return True


async def _raw_summarize(text: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})
    response = await acompletion(
        model=settings.LLM_SUMMARIZE_MODEL,
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content


async def summarize(text: str, system_prompt: str | None = None, priority: int = 2) -> str:
    fut = await llm_queue.submit_task(priority, _raw_summarize, text, system_prompt=system_prompt)
    return await fut


async def _raw_deep_analysis(text: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})
    response = await acompletion(
        model=settings.LLM_ANALYSIS_MODEL,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content


async def deep_analysis(text: str, system_prompt: str | None = None, priority: int = 2) -> str:
    fut = await llm_queue.submit_task(priority, _raw_deep_analysis, text, system_prompt=system_prompt)
    return await fut


async def _raw_get_embedding(text: str) -> list[float]:
    try:
        response = await aembedding(
            model=settings.LLM_EMBED_MODEL,
            input=[text],
            dimensions=768,
        )
        return response.data[0]["embedding"]
    except Exception as primary_exc:
        fallback_model = settings.LLM_EMBED_FALLBACK_MODEL
        if fallback_model:
            logger.warning(
                "Primary embedding model %s failed. Falling back to %s. Error: %s",
                settings.LLM_EMBED_MODEL, fallback_model, primary_exc
            )
            try:
                response = await aembedding(
                    model=fallback_model,
                    input=[text],
                    dimensions=768,
                )
                return response.data[0]["embedding"]
            except Exception as fallback_exc:
                logger.error("Fallback embedding model %s also failed: %s", fallback_model, fallback_exc)
                raise fallback_exc
        raise primary_exc


async def get_embedding(text: str, priority: int = 2) -> list[float]:
    fut = await llm_queue.submit_task(priority, _raw_get_embedding, text)
    return await fut