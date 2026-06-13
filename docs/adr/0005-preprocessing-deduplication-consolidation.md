# Consolidated Pre-processing and Deduplication

We decided to consolidate content-based deduplication into the News Pre-processing stage, removing the standalone deduplication task. 

### Context & Problem
Originally, the pipeline had a separate "Deduplication" task that ran periodically to match article content hashes and link duplicates. However, this introduced a race condition: newly fetched articles would bypass pre-processing if they were marked as processed/relevant immediately, or would remain in the queue waiting for the scheduler to trigger the separate deduplication task. Having two independent triggers made pipeline scheduling complex and prone to ordering errors.

### Decision
1. **Consolidated Flow**: Content-based deduplication is executed on-the-fly during the News Pre-processing stage before LLM checks are performed.
2. **Batch Safety**: The pre-processing task commits changes per-article in its loop. If duplicate articles are processed in the same batch, the first article is processed and committed, and subsequent duplicate articles immediately detect it via their content hashes, mark themselves as duplicates, and skip the LLM check.
3. **Removed Stage**: The standalone deduplication task, its scheduler configuration, trigger routes, and UI trigger buttons were completely removed to simplify the pipeline.

### Future Considerations (Failure & Retry Handling)
- **Problem**: If the LLM relevance check fails (e.g., due to temporary network issues or safety blocks), the article is rolled back and remains with `is_relevant = None`, meaning it will be retried in subsequent runs. If an article consistently crashes the LLM (a "poison pill"), it could perpetually clog the pre-processing queue.
- **Proposed Refactoring**: Introduce a `preprocessing_attempts` counter on `NewsArticle` (defaulting to 0) and increment it on each pre-processing run. If attempts exceed a threshold (e.g., 3), mark the article as `is_relevant = False` to prevent it from clogging the queue, logging a system warning.
