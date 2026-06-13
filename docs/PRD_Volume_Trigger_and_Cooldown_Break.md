# PRD: Task Volume Triggers and Cooldown Breaks

## Problem Statement

Currently, the NewsAgent background task executions (such as News Pre-processing and AI Analysis) are triggered either manually or on a fixed interval/cron schedule. This is inefficient when incoming news volume fluctuates. If news inflow is low, the pipeline runs needlessly; if news inflow is high, the backlog accumulates until the next schedule run. 

To improve responsiveness and resource efficiency, the system needs a new "trigger by volume" mode that automatically starts processing tasks once a certain volume of pending articles is reached. Furthermore, to protect system resources (especially local Ollama instances running on GPU/CPU) from runaway executions, a cooldown "break time" is required to prevent tasks from triggering repeatedly without rest.

## Solution

1. **Volume-Based Triggering**: Support automatic task execution triggered when the volume of data in a given step reaches a configured threshold (running alongside schedule-based triggers as a fallback).
2. **Cooldown (Break Time)**: Enforce a rest period following any task run during which the task cannot be re-executed, even if the schedule fires or the volume threshold is met.
3. **Configuration & Dashboard UI**: Expose the volume threshold and cooldown minutes in the database, API endpoints, and Settings Page UI, allowing granular settings for each job.

## User Stories

1. As a system operator, I want the pre-processing task to trigger automatically when the number of raw, un-preprocessed articles reaches a threshold (e.g., 10 articles), so that articles are filtered promptly.
2. As a system operator, I want the AI analysis task to trigger automatically when the number of relevant pending articles reaches a threshold (e.g., 5 articles), so that insights are updated in near real-time.
3. As a resource manager, I want to define a cooldown break time (in minutes) for each job, so that the local GPU/CPU is not continuously pinned at 100% load.
4. As an operator, I want scheduled triggers to remain active even when volume triggers are enabled, so that backlog data is still processed even if the volume threshold is never reached.
5. As a developer, I want the system to check volume triggers periodically and after any ingestion task, so that downstream processing runs as soon as data is ready.
6. As a dashboard user, I want to edit the volume threshold and cooldown minutes for each background job on the Ingestion Scheduler page, so that I can easily tune pipeline pacing.
7. As a system administrator, I want cooldowns to be enforced after success, failure, or timeout runs, so that the system is guaranteed to rest in all scenarios.
8. As a developer, I want to view the configured volume thresholds and cooldown parameters in the `/api/scheduler/jobs` response, so that the frontend can display them.

## Implementation Decisions

* **Database Columns**:
  * Extend `JobConfig` with `volume_threshold` (Integer, nullable) and `cooldown_minutes` (Integer, default 5, not null).
* **Cooldown and Running Guards**:
  * Update `run_job_wrapper` to query active `TaskRun` states and block runs if another instance of the job is already running or if the time since the last run's completion is less than `cooldown_minutes`.
* **Volume Check Worker**:
  * Implement a fast background checker running every 30 seconds that queries pending backlog counts:
    * For `preprocessing`: count of `NewsArticle` where `is_relevant` is `None`.
    * For `analysis`: count of `NewsArticle` where `is_relevant` is `True` and no `AnalysisResult` exists.
  * If a job is enabled, not running, not in cooldown, and its pending count exceeds the threshold, trigger the job automatically.
* **API Endpoints**:
  * Update `JobConfigResponse` and `JobConfigUpdate` schemas in the FastAPI scheduler route to include `volume_threshold` and `cooldown_minutes`.
* **UI Controls**:
  * Add input fields for **Volume Trigger Threshold** and **Cooldown Minutes** inside the `JobCard` component in the Next.js Settings page.

## Testing Decisions

* **Seams to Test**:
  * **Cooldown Enforcement**: Test `run_job_wrapper` using a mock database session to verify it blocks execution when `last_run_time + cooldown_minutes` is in the future.
  * **Running State Guard**: Test `run_job_wrapper` to ensure it blocks new executions when there is an active `TaskRun` in `running` status.
  * **Volume Trigger Calculation**: Test the volume checking function by inserting different numbers of mock articles into the database and verifying that the target task is triggered only when the threshold is exceeded.
* **Prior Art**:
  * Refer to `tests/test_model_quota.py` for mocking LLM/scheduler states and database sessions.
  * Refer to `tests/test_pipeline_timeout.py` for testing run duration constraints and TaskRun state transitions.

## Out of Scope

* Volume-based triggers for news ingestion jobs (`rss_news`, `newsapi`, `collector_news`) or daily briefings (`briefing`).
* Dynamic adjustment of the 30-second volume check frequency.
* Real-time WebSocket pushes of volume trigger state to the frontend (polling is sufficient).

## Further Notes

* The database migration must set default values for existing rows (`volume_threshold = NULL` and `cooldown_minutes = 5`).
