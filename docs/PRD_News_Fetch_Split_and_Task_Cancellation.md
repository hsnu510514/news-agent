# PRD: News Fetch Split & Task Cancellation

## Problem Statement

Currently, the news fetching background tasks (RSS, NewsAPI, Collector) execute two distinct stages sequentially:
1. Ingesting raw articles from the external news APIs/feeds.
2. Performing LLM-based relevance checking and summarization on each article.

Because relevance checking calls expensive LLM APIs, it can take up to several minutes per ingestion run. The user cannot follow the latest progress of the news ingestion since the task run remains in the `"running"` state for a long time without granular feedback. Additionally, the system lacks any control mechanism to stop/cancel a long-running execution once it is started.

Finally, the current Next.js dashboard task processing status panel is cluttered and redundant, separating the active progress from the historical execution log table and separating the backlog counts.

## Solution

1. **Split News Fetching and Pre-processing**:
   - Ingestion tasks (RSS, NewsAPI, Collector) will do fast HTTP calls and URL-based deduplication, then write all new articles to the database with `is_relevant = null`. These fetching tasks will finish in seconds.
   - Introduce a new background task: **News Pre-processing** (`preprocessing`). This task runs at a scheduled interval (e.g. 10 minutes) or can be triggered manually. It processes pending articles (where `is_relevant` is `None`), performs content-based exact deduplication, and runs the LLM relevance check. It commits progress incrementally.

2. **Add Database-Backed Stop/Cancellation Control**:
   - Provide an API endpoint `POST /api/tasks/{task_run_id}/stop` that updates a task's status in the database to `"failed"` with the message `"Stopped by user"`.
   - The loop inside long-running tasks (`preprocessing` and `analysis`) checks the database status of its task run before processing each article. If stopped, it breaks early, preserving all progress made up to that point.

3. **Unified Task UI in Next.js**:
   - Remove the standalone status panel system-wide (Home page, Settings page, Tasks page).
   - In the Tasks page, display backlog metrics (Pending Pre-processing, Pending Analysis, Total News) in the Historical Executions Log card header.
   - Display a real-time progress bar, live duration timer (counting up in seconds), and a `"Stop"` button directly inside the row of the active task in the executions log table.

## User Stories

1. As an investment researcher, I want news fetching to complete in seconds, so that I don't have to wait for LLM processing to see that raw articles have been successfully fetched.
2. As an administrator, I want fetched articles to be stored in a pending state, so that I can see the exact size of the incoming queue (backlog) waiting to be filtered.
3. As a researcher, I want a separate pre-processing task to run in the background, so that relevance checking and content-based deduplication are decoupled from fetching.
4. As an operator, I want to see the real-time progress of the pre-processing task, so that I know how many pending articles have been processed out of the total backlog.
5. As a budget manager, I want content-based deduplication to run before the LLM check in pre-processing, so that we do not pay for redundant LLM calls on syndicated news.
6. As a researcher, I want duplicate and irrelevant news to be discarded or marked as irrelevant (`is_relevant = false`) with their content cleared, so that we save database storage space.
7. As an operator, I want to be able to click a "Stop" button on a running pre-processing or analysis task, so that I can halt it immediately if it is consuming too many resources.
8. As an operator, I want stopped tasks to preserve already processed articles, so that we do not lose work or waste API tokens that have already been paid for.
9. As a researcher, I want to see a live timer counting up the execution duration of the active task in the log table, so that I know exactly how long the task has been running.
10. As a researcher, I want the home and settings pages to be free of the redundant processing status panel, so that the UI remains clean and focused on content and settings.
11. As a researcher, I want to see the pending pre-processing backlog and the pending analysis backlog separately in the log table card header, so that I have full visibility into the stages of the data pipeline.

## Implementation Decisions

- **Schema fields**: NewsArticle `is_relevant` is defined as a nullable boolean (in Python, `bool | None`), where `None` indicates pending pre-processing, `True` indicates relevant, and `False` indicates irrelevant or duplicate.
- **Deduplication flow**: Keep fast URL-based deduplication at fetch time. Perform content-hash deduplication during the new `preprocessing` task by matching `content_hash` against already processed articles.
- **Cancellation interface**: A database-backed cancellation check is executed before processing each article in the loop. The stop button updates the task's database row status to `"failed"` with the message `"Stopped by user"`, triggering the loop abort.
- **Task history UI**: Active execution parameters (progress, live timer, stop button) are rendered inline in the top row of the history log table when a task status is `"running"`.
- **System stats API**: The task stats endpoint is updated to return distinct counts for both the pre-processing backlog and the AI analysis backlog.

## Testing Decisions

- **Seam**: Backend service level. Mock LLM relevance calls and database sessions in pytest.
- **Pre-processing Ingest Test**: Test that articles inserted with `is_relevant = None` are correctly picked up, duplicate contents are flagged as duplicates, and the LLM relevance check updates `is_relevant` to `True` or `False`.
- **Task Stop Test**: Trigger `run_analysis_pipeline` or `run_preprocessing_pipeline`, simulate a stop API call during execution, and assert that the loop breaks early and the database status updates correctly.
- **Prior Art**: Ingest tests (`tests/test_ingest.py`), deduplication tests (`tests/test_dedup.py`), and pipeline tests (`tests/test_pipeline.py`).

## Out of Scope

- Semantic deduplication based on vector embeddings during the fetch phase (this remains inside the AI analysis pipeline).
- Auto-restart of stopped tasks from where they left off (the next manual trigger or schedule run will naturally pick up any pending articles).
- Real-time websocket notifications for progress updates (the frontend will continue to use polling via SWR, with faster polling intervals when a task is running).

## Further Notes

- The database migrations are not affected since `is_relevant` was already nullable in the database.
