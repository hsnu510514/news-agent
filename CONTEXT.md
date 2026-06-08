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
_Avoid_: notification, warning, flash news, market wire

**Market Wire**:
Raw, real-time news updates streamed directly from third-party outlets without LLM analysis or synthesis.
_Avoid_: flash news, raw alert, notification feed

**Daily Briefing**:
A synthesized summary report generated every morning, highlighting key updates and changes in the Insight Vault over the previous 24 hours.
_Avoid_: daily report, newsletter, morning summary

**Entity Glossary**:
A translation dictionary containing bilingual names and tickers for companies, industries, macro entities, and technical terms to ensure consistency.
_Avoid_: translation dictionary, name mapping

**Task Execution**:
A single execution run of any background process (such as news fetching, deduplication, AI analysis, or briefing generation), whether scheduled or manually triggered.
_Avoid_: job run, task run, scheduler run

