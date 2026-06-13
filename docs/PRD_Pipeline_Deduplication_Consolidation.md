# PRD: Consolidating Deduplication into News Pre-processing

## Problem Statement
The background pipeline currently contains both a "Deduplication" job and a "News Pre-processing" job. Since both jobs perform content-based deduplication, this redundancy introduces unnecessary database queries, overlapping scheduler runs, and UI clutter (multiple manual trigger buttons on the Tasks page). 

Additionally, because `NewsArticle.is_relevant` previously defaulted to `True` on the database model, newly fetched articles bypassed pre-processing entirely, resulting in articles going straight to the AI Analysis phase without content deduplication or LLM relevance filtering. We need to consolidate deduplication into the pre-processing stage, ensure articles correctly default to pending pre-processing, reset affected un-preprocessed articles, and remove the redundant standalone deduplication job.

## Solution
1. **Model Default Fix**: Remove the `default=True` from `is_relevant` on the `NewsArticle` database model, allowing new articles to default to `None` (NULL) representing "pending pre-processing".
2. **Backlog Resumption**: Run a migration update to reset any existing articles that have `is_relevant = True` but have not been processed by the AI Analysis pipeline (i.e. no associated `AnalysisResult`) back to `is_relevant = None` so they correctly flow through pre-processing.
3. **Consolidated Pre-processing**: Ensure the pre-processing job computes content hashes and performs exact content deduplication incrementally on pending articles before calling LLM relevance checks.
4. **Purge Standalone Deduplication**: Remove the `dedup` job from the background scheduler, delete the `/api/scheduler/jobs/dedup/trigger` API route, and remove the "Deduplication" button from the Tasks page in the dashboard.
5. **Historical Content Hash Ingestion**: Run a script to backfill `content_hash` for any existing processed articles that lack it, ensuring future incoming articles can be accurately matched against them.

## User Stories
1. As an operator, I want all content-based deduplication to happen automatically during pre-processing, so that we don't call the LLM for duplicate articles.
2. As a dashboard user, I want a clean Tasks page with only the necessary trigger buttons, without a redundant "Deduplication" button.
3. As a developer, I want the scheduler configuration to be simplified by having one unified pre-processing job instead of separate pre-processing and deduplication runs.
4. As an operator, I want un-preprocessed backlog articles to correctly show up in the "Pending Pre-processing" queue, rather than bypassing the filters and going straight to analysis.

## Implementation Decisions
- Remove the `dedup` job from the default jobs list and the job execution wrapper in `jobs.py`.
- Remove the `/api/scheduler/jobs/dedup/trigger` route from `trigger.py`.
- Remove the "Deduplication" trigger button from the Next.js Tasks page `page.tsx` and adjust `page.test.tsx` to remove its assertion.
- Update `test_task_history.py` to target the `preprocessing` job instead of `dedup` in its execution tests.
- Update `NewsArticle` model in `schema.py` to remove `default=True` for the `is_relevant` column.

## Testing Decisions
- Run the full `pytest` suite ensuring all 106 tests (especially pipeline, task history, and pre-processing tests) pass.

## Out of Scope
- A separate database table for content deduplication history.
