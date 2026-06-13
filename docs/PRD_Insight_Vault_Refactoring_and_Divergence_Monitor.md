# PRD: Insight Vault Refactoring and Divergence Monitor

## Problem Statement

The NewsAgent platform successfully processes global financial and policy news into bilingually synthesized subjects, insights, and facts. However, the current Insight Vault explorer page displays a very small subset of insights (limited to the first 20 updated items) and fails to let users search or filter across the complete dataset because filtering is done client-side on this truncated list. Furthermore, the ingestion pipeline occasionally produces duplicate or fragmented subjects and insights (e.g. "Nvidia" vs "NVDA"), and there is currently no way to monitor or visualize this topic fragmentation.

## Solution

Refactor the Insight Vault explorer and Settings dashboard:
1. Refactor the backend insights API to support server-side filtering (by subject type, sub-category tag, and search query) and pagination.
2. Update the frontend Insight Vault explorer page to execute server-side queries and paginate through results, preventing truncation.
3. Build a dynamic cascade filter on the frontend: selecting a Subject Type (Ticker, Macro, Theme) dynamically queries the backend for the top 15 most frequent tags to serve as sub-category filter options.
4. Implement a Divergence Monitor tab in Settings to list potential duplicate subjects (based on name similarity) and duplicate insights (based on semantic similarity of summaries under the same subject), enabling data-driven tracking of topic fragmentation.

## User Stories

1. As a research analyst, I want the Insight Vault explorer to load all insights rather than being truncated to the top 20, so that I don't miss critical narrative developments.
2. As a research analyst, I want to filter insights by Subject Type (Ticker, Macro, or Theme), so that I can quickly narrow down the field of study.
3. As a research analyst, I want to see a secondary sub-category filter that dynamically updates with the top 15 most frequent tags when I select a Subject Type, so that I can filter within popular sectors or macro themes without being overwhelmed by hundreds of options.
4. As an investor, I want to run a search query that filters insights across the entire database server-side, so that I can find specific tickers or dimensions that aren't on the first page.
5. As a research analyst, I want to paginate through the Insight Vault using Next and Previous buttons, so that I can navigate through hundreds of insights sequentially.
6. As a research analyst, I want the search filters, sub-categories, and page numbers to update the URL query parameters (or fetch state) correctly, so that the view is always synchronized with my search criteria.
7. As an administrator, I want to see a "Divergence Monitor" tab in the Settings page, so that I can assess the health and consistency of our ingested data.
8. As an administrator, I want the Divergence Monitor to display a table of potential duplicate subjects with similarity scores, so that I can see when different naming variations (e.g. "Apple" vs "AAPL") have fragmented our subject database.
9. As an administrator, I want the Divergence Monitor to display a table of potential duplicate insights under the same subject, so that I can detect when the ingestion pipeline has created redundant narrative dimensions (e.g., "Q1 Earnings" vs "Q1 Results").

## Implementation Decisions

- **API and Backend Service**:
  - The list insights endpoint will be modified to support query parameters: `subject_type`, `tag`, `q` (search query), `limit`, and `offset`.
  - The search query `q` will filter against `Subject.name` and `Insight.dimension_name` using case-insensitive SQL matching.
  - A new endpoint `GET /api/insights/top-tags` will be added. It accepts a `subject_type` and returns a list of the top 15 most frequent tags used in subjects of that type.
  - A new endpoint `GET /api/insights/divergence` will be added. It returns potential duplicate subjects (Levenshtein name similarity $\ge 80\%$) and potential duplicate insights (summary text/vector similarity $\ge 0.85$ under the same subject).
- **Frontend State and Filtering**:
  - The frontend page will switch from local React state array filtering to API-based server-side querying using SWR.
  - The cascade filter dropdown will trigger SWR fetches to `/api/insights/top-tags` whenever the `subject_type` changes.
  - SWR key will include the query parameters to trigger automatic refetches when parameters change.
- **Admin Settings**:
  - A new tab named "Divergence Monitor" will be added to the Settings tabbed view, alongside Ingestion Scheduler and Entity Glossary.
  - It will display tables for potential duplicates returned by the divergence API.

## Testing Decisions

- **Testing Seam**:
  - **FastAPI Backend Tests**: Verify endpoint request validation and SQL queries by writing tests under the backend test suite, mimicking `tests/test_pipeline.py` database mock sessions and routes tests.
  - **Next.js Compilation**: Verify typescript and build safety by running `npm run build` in the `dashboard/` directory.
  - **Manual/Interactive Testing**: Run the backend and frontend dev servers to interactively verify cascade dropdown tag loading, server-side search, page pagination, and Settings Divergence Monitor rendering.

## Out of Scope

- Automatic merging or deletion of duplicate subjects/insights. (This iteration is for monitoring and gathering data first).
- Editing or modifying subjects/insights directly from the Divergence Monitor table.
- User authentication and multi-user views.

## Further Notes

- Respect the glossary terms defined in `CONTEXT.md` (e.g. refer to "Divergence Monitor", "Insight Vault").
