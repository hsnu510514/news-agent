# PRD: Frontend Integration of Backend Intelligence & Settings Tabs

## Problem Statement

The NewsAgent platform has successfully built robust backend capabilities—including the bilingual Insight Vault, Daily Briefings, Emergency Alerts, Market Wire feeds, and an Entity Glossary—but these are currently not displayed or accessible to users on the frontend dashboard. The current dashboard page incorrectly queries a non-existent `/api/flash` endpoint, uses outdated terminology (such as "Flash News" instead of "Market Wire"), and lacks the visual widgets, search filters, and pages required to leverage the platform's full investment research value.

## Solution

Redesign and expand the Next.js frontend to fully integrate and display all backend intelligence and administrative features. This includes:
1. Revamping the main Dashboard page to include a bilingually-toggleable Daily Briefing widget and an Emergency Alerts warning banner.
2. Implementing a global Semantic Search bar queryable against the Insight Vault and news articles.
3. Creating a dedicated Insight Vault explorer page to navigate Subjects, Insights, and supporting Facts.
4. Correcting the "Flash News" view to use the "Market Wire" glossary terminology and fetch from `/api/market-wire`.
5. Redesigning the Settings page to feature a tabbed interface containing (a) the Ingestion Scheduler, and (b) the Entity Glossary management interface (list, create, update, verify).
6. Elevating the visual design to feel premium, utilizing dynamic micro-animations, clean dark/light UI tokens, and harmonious colors, adhering strictly to Tailwind v4, global CSS, and Shadcn UI.

## User Stories

1. As a research analyst, I want to see a clear, high-impact Emergency Alerts banner at the top of the dashboard whenever there is a critical global market shock, so that I can react immediately to time-sensitive events.
2. As a research analyst, I want the Emergency Alerts banner to display bilingual (English & Chinese) information, so that I can quickly read the context regardless of my language preference.
3. As an investor, I want to read the Daily Briefing summary and key takeaways at the top of my dashboard every morning, so that I can get a rapid update on the previous 24 hours of market insights.
4. As an investor, I want to toggle the Daily Briefing between English and Chinese summaries, so that I can review key insights in my preferred language.
5. As an analyst, I want to run a semantic search from the dashboard using natural language queries, so that I can find related news, subjects, and insights even if my exact keywords do not match the database fields.
6. As a researcher, I want to explore the Insight Vault via a dedicated page showing Subjects (Tickers, Macro indicators, Themes), so that I can see the synthesized intelligence organized by topics.
7. As a researcher, I want to view the list of narrative Dimensions (Insights) under each Subject, along with their urgency and sentiment badges, so that I can understand the market's bias on that topic.
8. As a researcher, I want to expand any Insight to view a timeline of supporting bilingual Facts, so that I can audit the specific data points backing up the AI's synthesis.
9. As a researcher, I want to click on a Fact's source article link, so that I can open the original news page in a new window for deep-dive reading.
10. As a trader, I want to view a real-time stream of raw Market Wires on a dedicated page, so that I can watch the un-synthesized wire feeds as they happen.
11. As a developer, I want the Market Wire page to fetch from `/api/market-wire` rather than a non-existent `/api/flash` endpoint, so that the page loads actual data instead of returning a 404 error.
12. As a content manager, I want to manage the bilingual translation dictionary in the Settings page via an Entity Glossary tab, so that I don't need direct database access to verify or update terms.
13. As a content manager, I want to see a list of verified and unverified glossary terms, so that I know which mappings have been validated by human oversight.
14. As a content manager, I want to add new glossary terms or edit existing ones via a form in the Entity Glossary tab, so that I can easily expand the bilingual mapping dictionary.
15. As a content manager, I want to click a "Verify" button next to any unverified glossary term, so that it becomes marked as verified and ensures bilingual consistency.
16. As an administrator, I want to toggle and reschedule active crawler cron/interval jobs on a dedicated Ingestion Scheduler tab in settings, so that I can manage crawling frequencies from the UI.

## Implementation Decisions

- **API Integration (`dashboard/src/lib/api.ts`)**: Add explicit types and fetchers for `DailyBriefing`, `Insight`, `InsightFact`, `EntityGlossary`, and `MarketWire`. Replace references to the obsolete `/api/flash` with `/api/market-wire`.
- **Navigation Menu (`dashboard/src/components/sidebar.tsx`)**: Update navigation paths. Add "Insight Vault" (`/insights`) and rename "Flash" to "Market Wire" (`/market-wire`).
- **Dashboard (`dashboard/src/app/page.tsx`)**: Integrate the `/api/alerts` banner at the top, a bilingual toggle widget for `/api/briefings/latest`, a semantic search component calling `/api/analysis/search`, and polished statistics and news layouts.
- **Insight Vault Explorer (`dashboard/src/app/insights/page.tsx`)**: Implement a filterable dashboard for subjects and insights, displaying color-coded sentiment badges and collapsible lists of supporting facts.
- **Market Wire Feed (`dashboard/src/app/market-wire/page.tsx`)**: Replaces the `/flash` page, querying `/api/market-wire`.
- **Two-Tab Settings Layout (`dashboard/src/app/settings/page.tsx`)**: Use a tabbed component to divide the Ingestion Scheduler and the Entity Glossary management interface.

## Testing Decisions

- **Seams for Testing**:
  - **Build Verification**: Run `npm run build` within the dashboard directory to guarantee zero typescript or build-time compilation errors.
  - **Mock Data Verification**: Verify that the API functions in `api.ts` correctly handle various states (empty lists, null values, network failures).
  - **Manual/Interactive Verification**: Verify responsiveness, English/Chinese toggles, form submissions (saving/verifying glossary terms), and routing consistency.
- **Prior Art**: The existing FastAPI python tests under `tests/` (e.g., `test_alerts.py`, `test_briefing.py`, `test_glossary.py`, `test_market_wire.py`) can be used as references for the API response schemas.

## Out of Scope

- Backend modifications: The backend API endpoints are already built and tested. No changes to DB schemas, SQLAlchemy models, or FastAPI routers should be introduced unless absolutely required for bug fixes.
- User authentication and multi-user tenancy: The settings and scheduler configurations will remain globally editable by any user accessing the local dashboard.

## Further Notes

- Respect the glossary terms defined in `CONTEXT.md` (e.g. refer to "Market Wire" and "Emergency Alerts" instead of "Flash News").
- Use clean modern design accents: subtle gradients, dark-mode styling (background matching Next.js dark default theme), and rounded/harmonized cards.
