# NewsAgent

An AI-powered investment research agent that automatically ingests, analyzes, and serves financial news and global affairs insights in Chinese and English.

## Language

**Global Affairs & Macro Policy**:
A topic category covering geopolitics, international trade, central bank policies, national regulatory updates, and major election outcomes.
_Avoid_: politics, political news, general policy

**Financial News**:
A topic category covering corporate earnings, stock market performance, sector trends, and company-specific announcements.
_Avoid_: business news, stock news

**Primary Source**:
A news agency or outlet that generates original reporting or wire feeds.
_Avoid_: source, news origin

**Collector Ingest**:
An ingestion channel that polls the custom self-hosted Collector API to incrementally sync news articles from multiple aggregated feeds.
_Avoid_: collector sync, rsshub sync

**Syndicated Content**:
Articles republished or repackaged by secondary outlets that cite or reprint a Primary Source with minimal changes.
_Avoid_: duplicate news, reprint

**Insight Vault**:
The centralized repository of synthesized topic and entity insights, updated incrementally as new news is analyzed.
_Avoid_: knowledge base, memory pool

**Insight**:
A distinct narrative thread or dimension under a Subject, supported by a cluster of news articles and specific facts. A single Subject can have multiple Insights.
_Avoid_: analysis, report

**Emergency Alert**:
A high-impact, immediate geopolitical or financial shock (e.g. military conflict, trade tariffs, banking failures) that requires immediate user attention.
_Avoid_: notification, warning, flash news

**Daily Briefing**:
A synthesized summary report generated every morning, highlighting key updates and changes in the Insight Vault over the previous 24 hours.
_Avoid_: daily report, newsletter, morning summary

**Entity Glossary**:
A translation dictionary containing bilingual names and tickers for companies, industries, macro entities, and technical terms to ensure consistency.
_Avoid_: translation dictionary, name mapping

**Task Execution**:
A single execution run of any background process (such as news fetching, deduplication, AI analysis, or briefing generation), whether scheduled, manually triggered, or volume-triggered.
_Avoid_: job run, scheduler run
_Note_: The database schema uses the historical term `TaskRun` (`task_runs` table) to avoid breaking migrations. This alignment is deferred as planned technical debt.

**Volume Trigger**:
A trigger mechanism that automatically starts a Task Execution once the backlog count for that task (e.g., pending raw articles or pending relevant articles) reaches a specified threshold.
_Avoid_: quantity trigger, queue trigger

**Job Cooldown**:
A configurable rest period (break time) enforced after a task completes (succeeds, fails, or times out) during which the task cannot be re-executed, preventing CPU/GPU resource exhaustion.
_Avoid_: break time, lock time, task pause

**Timeout**:
An execution state where a Task Execution exceeds its maximum configured duration and is aborted by the system, saving a partial progress record.
_Avoid_: task abort, task kill

**News Pre-processing**:
A background task that filters newly fetched articles by performing content-based deduplication and LLM relevance checks, flagging duplicate or irrelevant articles and marking relevant ones as ready for AI analysis.
_Avoid_: ingestion processing, relevance filtering

**Analyzed News**:
An ingested news article that has been processed by the AI pipeline, generating sentiment, urgency, bilingual summaries, and topic tags.
_Avoid_: processed news, AI report, translated article

**Pending News**:
An ingested news article that is marked as relevant but has not yet been processed by the AI analysis pipeline (i.e. has no associated AnalysisResult).
_Avoid_: backlog, backlog news, unprocessed article

**Divergence Monitor**:
An administrative diagnostic view and API designed to detect and resolve potential duplicate subjects and duplicate insights in the Insight Vault (via merging or ignoring) using name similarity and vector embedding analysis.
_Avoid_: duplicate check, merge utility, duplicate report

**Two-Tier Fallback**:
A resilience strategy that redirects failed LLM tasks to a designated alternative model (a lightweight model for low-complexity filtering/summarization, or a reasoning model for high-complexity analysis) to prevent pipeline stalls.
_Avoid_: model failover, fallback routing


