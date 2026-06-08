# PRD: Syndicated News & Market Wire Separation

## Problem Statement

As a research user, I am overwhelmed by the volume of syndicated and duplicate news content. Processing every redundant article through LLM synthesis pipelines is highly expensive, causes API rate-limit exceptions, and results in duplicate facts under the same Insight. Additionally, the previous design used the forbidden term "flash news" and introduced naming and logical clashes with synthesized "Emergency Alerts" (which are high-urgency insights).

---

## Solution

Build a budget-friendly, sequential ingestion and analysis pipeline that:
1. Cleanly separates raw "Market Wires" (renamed from Flash News) from synthesized "Emergency Alerts" (Insights with urgency `flash`) to avoid database and terminology clashes.
2. Identifies "Syndicated Content" and links it to the "Primary Source" using exact content hashing and multilingual vector similarity (using `gemini/gemini-embedding-2`).
3. Flags syndicated copies as `is_relevant = False` and bypasses the expensive LLM analysis.
4. Excludes syndicated copies from the main `/api/news` feed by default while exposing them via a specialized `/api/news/syndicated` endpoint to power a duplicate/syndication panel in the dashboard UI.

---

## User Stories

1. As a research user, I want the system to ingest English and Chinese news feeds, so that I can monitor global financial and geopolitical events.
2. As a budget-conscious user, I want duplicate news articles (Syndicated Content) to be matched and linked without calling expensive LLM synthesis pipelines, saving API token costs.
3. As a researcher, I want to see which news articles are syndicated copies of a primary source and view them grouped together, so that I can track how a story is reported across different outlets.
4. As a developer, I want raw wire feeds (Market Wires) and synthesized alerts (Emergency Alerts) to use separate tables, routes, and naming conventions, so that there is no database/naming conflict between them.
5. As an API client, I want `/api/news` to exclude syndicated copies by default, so that my main news feed remains clean and free of duplicates.
6. As an API client, I want `/api/news/syndicated` to return a list of all syndicated articles along with their primary sources, so that I can populate the syndication panel in the UI.
7. As a system operator, I want the semantic deduplication threshold to handle cross-language matching correctly so that a Chinese reprint of an English article is properly identified.
8. As a developer, I want the embedding service to run asynchronously so that the sequential pipeline does not block on synchronous HTTP calls.

---

## Implementation Decisions

### Market Wire Rename
- Renamed the `FlashNews` model class to `MarketWire`.
- Renamed the table name from `flash_news` to `market_wires` and updated index names.
- Renamed `/api/flash` routes and files to `/api/market-wire` and `src/api/routes/market_wire.py` respectively.
- Updated terminology in `CONTEXT.md` to define **Market Wire** and forbid the term "flash news" under both Market Wire and Emergency Alert.

### Syndicated Content DB Linking
- Added a self-referential foreign key and relationship on `NewsArticle`:
  - `duplicate_of_id`: Foreign key pointing to `news_articles.id`.
  - `duplicate_of` / `syndicated_articles`: Relationships to retrieve the primary source or syndicated copies of an article.

### Hybrid Deduplication
- **Exact deduplication**: Instead of deleting duplicate articles (exact URL or content hash matches) in `deduplicate_news`, we order them by fetched time ascending, keep the first one as canonical, link duplicates to it via `duplicate_of_id`, and set their `is_relevant = False`.
- **Semantic deduplication**: In the sequential analysis pipeline, before calling the LLM, we generate the article's embedding and search Qdrant for similar processed articles. If a match is found with a cosine similarity score `>= 0.90` (or cross-language matching `>= 0.88`), we link `duplicate_of_id` to that article, set `is_relevant = False`, write a placeholder `AnalysisResult` (with `llm_model="semantic_dedup"`), and skip LLM analysis.

### API Routes
- **Exclusion in main feed**: Updated `/api/news` to filter out syndicated articles (where `duplicate_of_id` is not null) by default.
- **New Syndicated Endpoint**: Created `/api/news/syndicated` to return all syndicated articles alongside their parent primary sources.

### Embedding Model & Async Fix
- Upgraded default embedding model to `gemini/gemini-embedding-2` to support high-performance multilingual vectors.
- Fixed the `get_embedding` method in `llm.py` to use asynchronous `litellm.aembedding` instead of synchronous `litellm.embedding`.

---

## Testing Decisions

### Seams to Test
1. **Deduplication Linking**: Validate `deduplicate_news` to ensure exact hash/URL duplicates are linked via `duplicate_of_id` and flagged as irrelevant rather than deleted.
2. **Semantic Bypass**: Validate `process_article_sequentially` to ensure semantic duplicate articles skip LLM analysis and are saved with the correct relationships in the database.
3. **API Routing**: Verify `/api/news` filters out duplicates and `/api/news/syndicated` returns them with primary source details.

### Prior Art
- Existing tests in `tests/test_pipeline.py` and `tests/test_ingest.py` will serve as patterns for DB mocking and client requests.

---

## Out of Scope

- Real-time websocket notifications for syndicated content.
- User interfaces/frontend changes (this PRD specifies the backend models, database migrations, and API endpoints).
