from __future__ import annotations

import logging

import litellm
from litellm import acompletion, aembedding

from src.core.config import settings

import asyncio
import time
from datetime import date
from typing import Callable, Any

logger = logging.getLogger("news-agent")

litellm.suppress_debug_info = True


class DailyQuotaExhaustedError(Exception):
    """Raised when the Gemini API daily/persistent rate limit is exhausted."""
    pass


class ModelQuotaTracker:
    def __init__(self):
        # Maps model_name -> list of request timestamps (within last 60s)
        self._requests: dict[str, list[float]] = {}
        # Maps model_name -> list of tuples (timestamp, token_count)
        self._tokens: dict[str, list[tuple[float, int]]] = {}
        # Maps model_name -> daily count
        self._rpd_counts: dict[str, int] = {}
        # Maps model_name -> daily cost in USD
        self._costs: dict[str, float] = {}
        # Maps model_name -> daily prompt tokens
        self._prompt_tokens: dict[str, int] = {}
        # Maps model_name -> daily completion tokens
        self._completion_tokens: dict[str, int] = {}
        # Maps model_name -> date of last reset
        self._last_reset_dates: dict[str, date] = {}
        # Maps model_name -> status ("healthy", "rate_limited", "error")
        self._status: dict[str, str] = {}
        # Maps model_name -> last error message
        self._error_messages: dict[str, str] = {}

    def _reset_if_needed(self, model: str):
        today = date.today()
        if self._last_reset_dates.get(model) != today:
            self._rpd_counts[model] = 0
            self._costs[model] = 0.0
            self._prompt_tokens[model] = 0
            self._completion_tokens[model] = 0
            self._last_reset_dates[model] = today
            self._status[model] = "healthy"
            self._error_messages[model] = ""

    def record_request(
        self, 
        model: str, 
        token_count: int, 
        cost: float = 0.0, 
        prompt_tokens: int = 0, 
        completion_tokens: int = 0, 
        timestamp: float | None = None
    ):
        if timestamp is None:
            timestamp = time.time()
        self._reset_if_needed(model)
        
        # Record request timestamp
        if model not in self._requests:
            self._requests[model] = []
        self._requests[model].append(timestamp)
        
        # Record tokens
        if model not in self._tokens:
            self._tokens[model] = []
        self._tokens[model].append((timestamp, token_count))
        
        # Increment RPD
        self._rpd_counts[model] = self._rpd_counts.get(model, 0) + 1
        
        # Record cost and split tokens
        self._costs[model] = self._costs.get(model, 0.0) + cost
        self._prompt_tokens[model] = self._prompt_tokens.get(model, 0) + prompt_tokens
        self._completion_tokens[model] = self._completion_tokens.get(model, 0) + completion_tokens
        
        self._status[model] = "healthy"
        self._error_messages[model] = ""

    def record_failure(self, model: str, error_msg: str, timestamp: float | None = None):
        self._reset_if_needed(model)
        is_rate_limit = "429" in error_msg or "rate limit" in error_msg.lower() or "quota" in error_msg.lower()
        self._status[model] = "rate_limited" if is_rate_limit else "error"
        self._error_messages[model] = error_msg

    def get_rpm(self, model: str) -> int:
        now = time.time()
        reqs = self._requests.get(model, [])
        # Clean up older than 60s
        reqs = [t for t in reqs if now - t <= 60]
        self._requests[model] = reqs
        return len(reqs)

    def get_tpm(self, model: str) -> int:
        now = time.time()
        tokens = self._tokens.get(model, [])
        # Clean up older than 60s
        tokens = [item for item in tokens if now - item[0] <= 60]
        self._tokens[model] = tokens
        return sum(item[1] for item in tokens)

    def get_rpd(self, model: str) -> int:
        self._reset_if_needed(model)
        return self._rpd_counts.get(model, 0)

    def get_cost(self, model: str) -> float:
        self._reset_if_needed(model)
        return self._costs.get(model, 0.0)

    def get_prompt_tokens(self, model: str) -> int:
        self._reset_if_needed(model)
        return self._prompt_tokens.get(model, 0)

    def get_completion_tokens(self, model: str) -> int:
        self._reset_if_needed(model)
        return self._completion_tokens.get(model, 0)

    def get_status(self, model: str) -> str:
        self._reset_if_needed(model)
        return self._status.get(model, "healthy")

    def get_error_message(self, model: str) -> str:
        self._reset_if_needed(model)
        return self._error_messages.get(model, "")

    def reset_all(self):
        self._requests.clear()
        self._tokens.clear()
        self._rpd_counts.clear()
        self._costs.clear()
        self._prompt_tokens.clear()
        self._completion_tokens.clear()
        self._last_reset_dates.clear()
        self._status.clear()
        self._error_messages.clear()


# Instantiate singleton
model_quota_tracker = ModelQuotaTracker()


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
        self._quota_exhausted = False
        self._pacing_delay = None
        self.last_used_model = None
        self.backoff_factor = 2.0
        self.status_tracker = api_status_tracker

    @property
    def pacing_delay(self) -> float:
        # If we have an explicit override set on this queue instance (like in tests), use it
        if self._pacing_delay is not None:
            pacing_val = self._pacing_delay
        else:
            pacing_val = getattr(settings, "LLM_PACING_DELAY", "auto")

        if pacing_val == "auto":
            # Check last used model
            model = getattr(self, "last_used_model", None)
            if model:
                if model.startswith("gemini/"):
                    return 4.0
                else:
                    return 0.0
            # If no model is set yet, default to safe 4.0
            return 4.0
        
        try:
            return float(pacing_val)
        except (ValueError, TypeError):
            return 4.0

    @pacing_delay.setter
    def pacing_delay(self, value):
        self._pacing_delay = value

    async def submit_task(self, priority: int, func: Callable, *args, **kwargs) -> asyncio.Future:
        # Check if the day has changed since last reset to automatically reset and restart the queue
        if date.today() != self.status_tracker._last_reset_date:
            self.status_tracker.status = "healthy"
            self.status_tracker.error_message = ""
            self.status_tracker.requests_made_today = 0
            self.status_tracker._last_reset_date = date.today()
            self._quota_exhausted = False
            self.start()

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        if self._quota_exhausted:
            error_msg = self.status_tracker.error_message or "LLM queue is not running due to daily quota exhaustion."
            future.set_exception(DailyQuotaExhaustedError(error_msg))
            return future

        self._seq += 1
        await self._queue.put((priority, self._seq, future, func, args, kwargs))
        return future

    def start(self):
        self._quota_exhausted = False
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
                            self._quota_exhausted = True
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


def check_budget_limit(model: str):
    # Ollama models are local/free and bypass budget checks
    if model.startswith("ollama/"):
        return
    
    total_cost = sum(model_quota_tracker.get_cost(m) for m in model_quota_tracker._costs.keys())
    if total_cost >= settings.DAILY_SPEND_LIMIT:
        raise DailyQuotaExhaustedError(
            f"Daily spend limit of ${settings.DAILY_SPEND_LIMIT:.2f} reached (Spent: ${total_cost:.4f})."
        )


async def tracked_acompletion(model: str, messages: list[dict], **kwargs) -> Any:
    if not model:
        raise ValueError("Model configuration is incomplete. Please configure your models in Settings.")
    check_budget_limit(model)
    llm_queue.last_used_model = model
    try:
        response = await acompletion(model=model, messages=messages, **kwargs)
        prompt_tokens = 0
        completion_tokens = 0
        cost = 0.0
        if hasattr(response, "usage") and response.usage:
            prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
        total_tokens = prompt_tokens + completion_tokens
        
        # Calculate cost using LiteLLM
        try:
            cost = litellm.completion_cost(response) or 0.0
        except Exception:
            pass

        model_quota_tracker.record_request(
            model=model,
            token_count=total_tokens,
            cost=cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
        return response
    except Exception as e:
        if not isinstance(e, DailyQuotaExhaustedError):
            model_quota_tracker.record_failure(model, str(e))
        raise e


async def tracked_aembedding(model: str, input: list[str], **kwargs) -> Any:
    if not model:
        raise ValueError("Model configuration is incomplete. Please configure your models in Settings.")
    check_budget_limit(model)
    llm_queue.last_used_model = model
    try:
        response = await aembedding(model=model, input=input, **kwargs)
        prompt_tokens = 0
        cost = 0.0
        if hasattr(response, "usage") and response.usage:
            prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
        elif hasattr(response, "data") and response.data:
            # Fallback estimation: ~1 token per 4 chars
            char_count = sum(len(text) for text in input)
            prompt_tokens = max(1, char_count // 4)
            
        # Calculate cost using LiteLLM
        try:
            cost = litellm.completion_cost(response) or 0.0
        except Exception:
            pass

        model_quota_tracker.record_request(
            model=model,
            token_count=prompt_tokens,
            cost=cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=0
        )
        return response
    except Exception as e:
        if not isinstance(e, DailyQuotaExhaustedError):
            model_quota_tracker.record_failure(model, str(e))
        raise e


# Raw LLM completion functions wrapped for the queue
async def _raw_classify(text: str, system_prompt: str | None = None) -> str:
    messages = []
    sys_prompt = system_prompt or ""
    json_instruction = "Return your response as a valid JSON object only. Do not include any text outside the JSON."
    if sys_prompt:
        sys_prompt = f"{sys_prompt}\n\n{json_instruction}"
    else:
        sys_prompt = json_instruction
        
    messages.append({"role": "system", "content": sys_prompt})
    messages.append({"role": "user", "content": text})

    try:
        response = await tracked_acompletion(
            model=settings.LLM_CLASSIFY_MODEL,
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as primary_exc:
        fallback_model = settings.LLM_REASONING_FALLBACK_MODEL
        if fallback_model and fallback_model != settings.LLM_CLASSIFY_MODEL:
            logger.warning(
                "Primary classification model %s failed. Falling back to %s. Error: %s",
                settings.LLM_CLASSIFY_MODEL, fallback_model, primary_exc
            )
            response = await tracked_acompletion(
                model=fallback_model,
                messages=messages,
                temperature=0.1,
            )
            return response.choices[0].message.content
        raise primary_exc


async def classify(text: str, system_prompt: str | None = None, priority: int = 2) -> str:
    fut = await llm_queue.submit_task(priority, _raw_classify, text, system_prompt=system_prompt)
    return await fut


async def _raw_check_relevance(text: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})
    try:
        response = await tracked_acompletion(
            model=settings.LLM_RELEVANCE_MODEL,
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as primary_exc:
        fallback_model = settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL
        if fallback_model and fallback_model != settings.LLM_RELEVANCE_MODEL:
            logger.warning(
                "Primary relevance model %s failed. Falling back to %s. Error: %s",
                settings.LLM_RELEVANCE_MODEL, fallback_model, primary_exc
            )
            response = await tracked_acompletion(
                model=fallback_model,
                messages=messages,
                temperature=0.1,
            )
            return response.choices[0].message.content
        raise primary_exc


async def check_relevance(title: str, summary: str, priority: int = 1) -> bool:
    import json
    system_prompt = (
        "You are an investment research filter. Analyze the news article title and summary.\n"
        "Determine if it is relevant to:\n"
        "1. Financial News (corporate earnings, stock market, company updates, sector trends, IPOs, mergers).\n"
        "2. Global Affairs & Macro Policy (geopolitics, trade, monetary/fiscal policy, regulations, central banks, elections).\n\n"
        "Return a JSON object with a single boolean field \"relevant\". Do not include any other text."
    )
    user_content = (
        f"Title: {title}\n"
        f"Summary: {summary or ''}"
    )
    try:
        fut = await llm_queue.submit_task(priority, _raw_check_relevance, user_content, system_prompt=system_prompt)
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
    try:
        response = await tracked_acompletion(
            model=settings.LLM_SUMMARIZE_MODEL,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as primary_exc:
        fallback_model = settings.LLM_LIGHTWEIGHT_FALLBACK_MODEL
        if fallback_model and fallback_model != settings.LLM_SUMMARIZE_MODEL:
            logger.warning(
                "Primary summarization model %s failed. Falling back to %s. Error: %s",
                settings.LLM_SUMMARIZE_MODEL, fallback_model, primary_exc
            )
            response = await tracked_acompletion(
                model=fallback_model,
                messages=messages,
                temperature=0.3,
            )
            return response.choices[0].message.content
        raise primary_exc


async def summarize(text: str, system_prompt: str | None = None, priority: int = 2) -> str:
    fut = await llm_queue.submit_task(priority, _raw_summarize, text, system_prompt=system_prompt)
    return await fut


async def _raw_deep_analysis(text: str, system_prompt: str | None = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": text})
    try:
        response = await tracked_acompletion(
            model=settings.LLM_ANALYSIS_MODEL,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as primary_exc:
        fallback_model = settings.LLM_REASONING_FALLBACK_MODEL
        if fallback_model and fallback_model != settings.LLM_ANALYSIS_MODEL:
            logger.warning(
                "Primary deep analysis model %s failed. Falling back to %s. Error: %s",
                settings.LLM_ANALYSIS_MODEL, fallback_model, primary_exc
            )
            response = await tracked_acompletion(
                model=fallback_model,
                messages=messages,
                temperature=0.2,
            )
            return response.choices[0].message.content
        raise primary_exc


async def deep_analysis(text: str, system_prompt: str | None = None, priority: int = 2) -> str:
    fut = await llm_queue.submit_task(priority, _raw_deep_analysis, text, system_prompt=system_prompt)
    return await fut


async def _raw_get_embedding(text: str) -> list[float]:
    try:
        response = await tracked_aembedding(
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
                response = await tracked_aembedding(
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