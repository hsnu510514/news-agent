# PRD: Prioritized LLM API Queue and Fail/Resume Recovery

## Problem Statement

As an operator of the NewsAgent system, I cannot easily verify if the AI analysis pipeline is running correctly or has crashed silently. Under Google AI Studio's Free Tier, model calls are strictly capped (e.g. 15 Requests Per Minute and 20 daily requests for Gemini 2.5/Pro). Because the background scheduler runs automatically, it quickly exhausts the daily API quota. Subsequent pipeline runs fail silently, recording a "success" status but analyzing 0 articles. Furthermore, concurrent manually triggered analysis runs conflict with scheduled jobs, and failed Daily Briefings cannot be manually regenerated once the quota resets.

---

## Solution

Implement an in-memory priority queue, automatic retries with backoff, fail/resume checkpointing, and a centralized system health API to make the system resilient to API rate limits and fully observable.

1. **Centralized Priority Queue**: Route all LiteLLM completion and embedding calls through a single `asyncio.PriorityQueue` in the backend. A background worker loop processes tasks one-by-one.
2. **Throttling & Retries**: Enforce a 4-second pacing delay between requests to stay below 15 RPM. Automatically retry transient errors (up to 3 times) with exponential backoff.
3. **Task Prioritization**:
   - **Priority 0 (High)**: Daily Briefing generation.
   - **Priority 1 (Medium)**: Manual queries and relevance checks.
   - **Priority 2 (Low)**: Standard news article ingest and analysis.
4. **Checkpointed Commits**: Save database transactions after each individual article is processed instead of committing once at the end of a batch.
5. **Early Aborts**: Stop execution of the remaining batch immediately if the queue worker encounters a hard daily quota exhaustion error.
6. **API Telemetry**: Maintain an in-memory `APIStatusTracker` recording connection status, used/remaining requests, and last error message.
7. **System Status Endpoint**: Add `GET /api/system/status` returning the health of the LLM API, Postgres, and Qdrant.
8. **Manual Briefing Trigger**: Add `POST /api/trigger/briefing` to allow manual recovery of daily briefings.

---

## User Stories

1. As an operator, I want all LLM requests to be prioritized, so that critical synthesis tasks like the Daily Briefing bypass standard news ingestion queues.
2. As a budget-conscious user on the Free Tier, I want the system to pace requests (e.g. 4s delay), so that I do not trigger 429 rate limit exceptions due to RPM caps.
3. As a developer, I want transient network glitches or temporary rate limits to be retried automatically with backoff, so that the pipeline does not fail on minor blips.
4. As an operator, I want the analysis pipeline to stop calling the API immediately if my daily quota is exhausted, so that I do not spam the API with guaranteed-to-fail requests.
5. As an operator, I want the analysis pipeline to commit database transactions after each article, so that successfully processed articles are saved even if the batch is aborted midway.
6. As a researcher, I want to manually trigger the Daily Briefing generation via the API once my quota resets, so that I can recover a briefing that failed during the night.
7. As an operator, I want to view a system status API endpoint, so that I can check connection status, current daily requests, and the last error message from the LLM provider.

---

## Implementation Decisions

### Modules to Modify
*   **LLM Interface (`src/core/llm.py`):** 
    *   Implement an `APIStatusTracker` class.
    *   Create a background queue worker task reading from a global `asyncio.PriorityQueue`.
    *   Redirect `classify`, `summarize`, `deep_analysis`, and `get_embedding` to submit tasks to the queue and await futures.
*   **Database & App Startup (`src/api/main.py`):**
    *   Initialize and start the background queue worker on app startup.
    *   Add a new router prefix `/api/system` with a `GET /status` endpoint querying the DB, Qdrant, and the `APIStatusTracker`.
*   **Analysis Loop (`src/analysis/classifier.py`):**
    *   Add a global `asyncio.Lock` for the pipeline.
    *   Move `session.commit()` inside the article loop.
    *   Gracefully abort execution on `DailyQuotaExhaustedError`.
*   **Trigger Endpoints (`src/api/routes/trigger.py`):**
    *   Add `/api/trigger/briefing` to run briefing generation.

---

## Testing Decisions

### Seams to Test
1.  **Priority Queue Dispatcher:** We will test the priority queue by submitting tasks of different priorities (0, 1, 2) concurrently and asserting that Priority 0 tasks are popped and processed first.
2.  **Retry and Abort Logic:** Mock the LiteLLM completion call to return a transient 429 error (asserting it retries) and then a permanent Daily Quota error (asserting it raises `DailyQuotaExhaustedError` and aborts).
3.  **FastAPI System Status Endpoint:** Query the `/api/system/status` endpoint to verify it returns database status, Qdrant status, and API tracker stats.

### Prior Art
*   None. (The `tests` folder is currently empty, so these tests will establish the baseline testing pattern for the project).

---

## Out of Scope
*   External notifications (Slack, Discord, Email) when the API key goes down.
*   Support for multiple concurrent active API keys (key rotation).
*   Automatic switching between different LLM providers mid-pipeline.
