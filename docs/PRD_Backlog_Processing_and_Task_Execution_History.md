# PRD: Backlog News Processing and Task Execution History Dashboard

## Problem Statement

As an operator of the NewsAgent system, the current fixed-size batch analysis (processing at most 20 articles every 30 minutes) is insufficient to keep up with the volume of incoming financial news and global affairs reporting. Consequently, the backlog of unprocessed articles continues to accumulate. While reducing feed sources helps mitigate the inflow, the background pipeline must be refactored to continually process pending news while protecting system resources from run-away executions or API quota limits. Furthermore, the existing dashboard lacks transparency, offering only a top status bar without a detailed execution history of active and completed tasks, making it difficult to debug or verify runs.

---

## Solution

1. **Iterative Backlog Processing Loop**: Modify the analysis pipeline to continually fetch and analyze pending articles in sequential batches until the backlog is cleared or resource limits are hit.
2. **Paced Execution Limits**: Add a configurable execution time limit (e.g. 25 minutes) and a batch size setting, placed within the Model Quotas & Allocation dashboard, allowing the pipeline to stop gracefully before overlapping with the next scheduler run.
3. **Paced Cancellation & Quota Grace**: Terminate the run gracefully if daily API quotas are exhausted, maintaining committed DB checkpoints for all successfully analyzed articles.
4. **"Timeout" Task Execution Status**: Record a distinct `timeout` status for Task Executions that terminate due to the execution time limit.
5. **Task Execution History Dashboard**: Add a dedicated "Task History" page to the Next.js frontend showing detailed active task status bars (with real-time progress indicators), past execution history logs (start time, end time, duration, processed counts, messages/errors), and manual run triggers for all background jobs.

---

## User Stories

1. As a system operator, I want the analysis pipeline to process pending news articles continually in a loop, so that the backlog of articles does not grow indefinitely.
2. As a resource manager, I want to configure a maximum execution duration (e.g. 25 minutes) for the analysis pipeline, so that a single execution run does not monopolize resources or run indefinitely.
3. As a developer, I want to configure the batch size retrieved from the database in each loop iteration, so that the memory and database connection footprint remains low.
4. As an operator, I want the pipeline to save database checkpoints after processing each individual article, so that a timeout or sudden quota abort does not lose already completed work.
5. As an operator, I want Task Executions that terminate due to the maximum duration limit to be marked with a `timeout` status rather than `success` or `failed`, so that I can easily differentiate them from complete or crashed runs.
6. As a researcher, I want a dedicated Task History page in the dashboard, so that I can see the comprehensive history of all background jobs (ingestion, deduplication, analysis, briefings).
7. As a researcher, I want to see a real-time progress bar of any active running task, so that I know exactly how many articles have been processed out of the total batch.
8. As a developer, I want to inspect execution tracebacks or reasons for failure/timeout for any historical run, so that I can diagnose system and API issues.
9. As an operator, I want to trigger any of the background tasks manually with a single click from the Task History page, so that I can manually force runs when needed.
10. As an operator, I want to configure the pipeline's maximum execution duration and batch size in the existing Model Quotas & Allocation tab, so that all pipeline constraints are managed in one place.

---

## Implementation Decisions

### Modules to Modify

* **Core Configuration**:
  * Extend settings to include max execution duration (minutes) and analysis batch size, ensuring they load from and save to the dynamic configuration JSON file.
* **API Endpoints**:
  * Expand system allocation APIs (`GET /api/system/models` and `PUT /api/system/models`) to accept and serve these two pipeline constraint parameters.
* **AI Analysis Pipeline**:
  * Refactor the sequential analysis pipeline to run in a loop.
  * In each loop iteration, fetch a batch of pending articles.
  * Check the elapsed time and quota exhaustion before processing each individual article. If a limit is hit, save current progress, update the Task Execution status to `"timeout"` or `"failed"`, and terminate the loop.
* **Job Scheduler**:
  * Update the scheduler run wrapper to make database updates conditional, preventing a `"timeout"` status from being overwritten with `"success"` upon clean function exit.
* **Frontend Navigation & Settings**:
  * Update the sidebar navigation to include a "Task History" link.
  * Update the Model Quotas & Allocation tab to support editing the new duration and batch size fields.
* **Frontend Task History Page**:
  * Create a new dashboard page displaying active execution status, real-time progress bar (processed/failed/total counts), a complete table/list of the 50 most recent executions, and manual trigger buttons for all scheduler jobs.

---

## Testing Decisions

### Seams to Test

* **Timeout & Recovery**: We will write tests that mock the elapsed run time to verify that the analysis pipeline stops exactly at the execution duration threshold, records a `"timeout"` status, and that subsequent runs successfully resume and process remaining articles.
* **Job Wrapper Status Protection**: We will test that when a job function exits normally but has written `"timeout"` to the database, the scheduler runner preserves that status rather than overwriting it to `"success"`.
* **API and Form Serializers**: Verify that the settings API correctly validates, reads, and writes the new configuration fields.

### Prior Art
* Database checkpointing and early-abort test structures in `tests/test_pipeline_checkpoint.py` and `tests/test_model_quota.py` will serve as the reference patterns.

---

## Out of Scope

* Real-time WebSocket subscriptions (the frontend will rely on paced SWR polling which automatically accelerates when a task is active).
* Editing cron expressions or trigger types directly from the Task History page (this remains in the Ingestion Scheduler settings).
* Dynamic cancellation/killing of active background threads via the API.
