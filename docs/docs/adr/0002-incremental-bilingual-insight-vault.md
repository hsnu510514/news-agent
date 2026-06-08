# Incremental Bilingual Insight Vault

We decided to structure our intelligence storage around a centralized "Insight Vault" mapping subjects to multiple narrative dimensions (Insights), each supported by a timeline of facts and raw news articles. Both raw articles and insights are stored bilingually (English & Chinese) in Postgres and embedded in Qdrant (Scenario B). To avoid cross-language semantic search mismatch, we generate and index English vectors for both English and Chinese content.
