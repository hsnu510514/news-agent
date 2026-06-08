# PRD: Bilingual News & Insight Agent (Insight Vault)

## Problem Statement

As a research user, I am overwhelmed by the volume of financial and geopolitical news syndicated across various sources. Ingesting and analyzing every raw article using LLMs leads to high API costs, duplicate content, and information overload. I need an automated agent that filters, deduplicates, and synthesizes global news in both English and Chinese into a structured **Insight Vault**, generating a **Daily Briefing** and highlighting **Emergency Alerts** without incurring high processing costs or database race conditions.

---

## Solution

Build an automated, budget-friendly bilingual news agent featuring:
1. **Title-Only Pre-Filtering:** Discarding irrelevant news before downloading full texts or calling expensive LLM pipelines.
2. **Bilingual Insight Vault:** Storing narrative threads (Insights) under Subjects (tickers, countries, themes) with a timeline of supporting facts, stored in Postgres and indexed in Qdrant using Scenario B.
3. **Sequential Pipeline Processing:** Processing articles one-by-one to avoid race conditions, duplicate insights, and LLM rate-limit exceptions.
4. **Emergency Alerts:** Surfacing critical geopolitical or financial shocks immediately at the top of the dashboard.
5. **Daily Briefing:** Automatically synthesizing a morning newsletter-style summary of the previous 24 hours' updates.
6. **Entity Glossary:** Maintaining a dynamic translation dictionary to guarantee consistent translation of company names, tickers, and technical terms.

---

## User Stories

1. As a research user, I want the system to ingest English and Chinese RSS feeds, so that I can monitor global financial and geopolitical events.
2. As a budget-conscious user, I want the system to pre-filter articles by title/description, so that I don't pay LLM costs for irrelevant sports, entertainment, or local news.
3. As a researcher, I want identical or near-duplicate news articles to be merged, so that I don't see the same story summarized multiple times under different outlets.
4. As an investor, I want news to be consolidated into specific narrative "Insights" under a "Subject" (like Nvidia or US Fed), so that I can see the timeline of facts for that narrative instead of a list of raw articles.
5. As a bilingual reader, I want all Insights and briefings to be stored and presented in both English and Chinese, so that I can read in my preferred language.
6. As an investor, I want to see critical, immediate market shocks (like military conflict or tariffs) at the top of my dashboard, so that I can react to them immediately.
7. As a researcher, I want a daily synthesized morning briefing (Daily Briefing) of the previous 24 hours' updates, so that I can quickly catch up on market events at the start of the day.
8. As an operator, I want to manage an Entity Glossary to verify name translations (like Nvidia to 英伟达), so that the LLM translates technical and company entities consistently.
9. As a developer, I want the news ingestion to run sequentially, so that I can avoid race conditions where parallel threads create duplicate insights for the same event.

---

## Implementation Decisions

### Modules to Build/Modify
*   **Database Schema (`src/models/schema.py`):** Create tables for `Subject`, `Insight`, `InsightFact`, `EntityGlossary`, and `DailyBriefing`. Add `is_relevant` to `NewsArticle`.
*   **Pre-Filtering Ingestion (`src/ingest/news_fetcher.py`):** Pre-screen RSS feed titles/summaries using Gemini 2.0 Flash to discard non-financial and non-geopolitical items before downloading full article text.
*   **Deduplication & Sequential Pipeline (`src/analysis/pipeline.py` & `classifier.py`):** Refactor the pipeline to process articles sequentially. Match articles against the Insight Vault using Qdrant semantic search (indexing English vectors). Decide if the article is `NO_CHANGE` (ignore), `UPDATE` (add fact to existing Insight), or `NEW` (create new Insight).
*   **Translation Mapping (`src/analysis/translation.py`):** Map incoming entities to verified glossary terms before prompting the LLM for updates/translation.
*   **Daily Briefing Job (`src/analysis/briefing.py`):** Fetch the last 24h updates and synthesize a structured daily brief using Gemini 2.5 Pro.
*   **FastAPI Routes (`src/api/main.py`):** Add endpoints for `/api/insights`, `/api/alerts`, `/api/briefings/latest`, and `/api/glossary`.

### Architectural Seams
*   **Database Level:** SQL database constraints and foreign keys will strictly cascade deletions on Insights and Facts.
*   **Vector Database (Scenario B):** Embeddings generated for both raw articles and active Insight summaries are indexed in Qdrant using 768-dimensional English vectors.

---

## Testing Decisions

### Seams to Test
1. **Pipeline Processing Loop:** We will test `process_article_sequentially` using mocked LLM completions and a mock database session to verify that duplicate news resolves to the same Insight, updates add new facts, and new topics spawn new Insights.
2. **FastAPI Web API Endpoints:** Test FastAPI routing and JSON structures using `httpx.AsyncClient` with a mock database context.

### Prior Art
*   None. (The `tests` folder is currently empty, so these tests will establish the baseline testing pattern for the project).

---

## Out of Scope
*   Real-time websocket pushing of Emergency Alerts.
*   User authentication or roles/permissions.
*   Automated trading executions or external webhook notifications.
