from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.llm import classify, summarize, deep_analysis, get_embedding
from src.storage.vectorstore import upsert_embedding, search_embeddings_with_filter
from src.analysis.translation import get_glossary_prompt_extension, register_detected_entities
from src.models.schema import (
    AnalysisResult,
    LanguageEnum,
    NewsArticle,
    SentimentEnum,
    UrgencyEnum,
    Subject,
    Insight,
    InsightFact,
    SubjectTypeEnum,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("news-agent")

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


async def analyze_article(article: NewsArticle) -> AnalysisResult:
    text = f"Title: {article.title}\n\n{article.content or ''}"
    language = article.language

    classify_prompt = _load_prompt("classify.yaml")
    classify_result = await classify(text=text, system_prompt=classify_prompt)

    classification = _parse_json(classify_result, {})

    topics = classification.get("topics", [])
    sentiment_raw = classification.get("sentiment", "neutral")
    sentiment_score = classification.get("sentiment_score", 0.0)
    urgency_raw = classification.get("urgency", "medium")
    companies = classification.get("companies_mentioned", [])
    market_impact = classification.get("market_impact", "")

    summarize_prompt = _load_prompt("summarize.yaml")
    summarize_result = await summarize(text=text, system_prompt=summarize_prompt)
    summaries = _parse_json(summarize_result, {})

    summary_en = summaries.get("summary_en", "")
    summary_zh = summaries.get("summary_zh", "")

    analysis_result = AnalysisResult(
        article_id=article.id,
        urgency=_safe_enum(UrgencyEnum, urgency_raw, UrgencyEnum.MEDIUM),
        sentiment=_safe_enum(SentimentEnum, sentiment_raw, SentimentEnum.NEUTRAL),
        sentiment_score=float(sentiment_score) if sentiment_score else 0.0,
        topics=topics,
        entities=_extract_entities(classification, companies),
        companies_mentioned=companies,
        summary_en=summary_en,
        summary_zh=summary_zh,
        impact_assessment=market_impact,
        llm_model="pipeline",
    )

    if summary_en:
        try:
            embedding = await get_embedding(summary_en)
            upsert_embedding(
                point_id=article.id,
                vector=embedding,
                payload={
                    "title": article.title,
                    "summary_en": summary_en,
                    "summary_zh": summary_zh,
                    "language": language.value,
                    "sentiment": sentiment_raw,
                    "topics": topics,
                    "source_name": article.source_name,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                },
            )
        except Exception:
            logger.exception("Failed to create embedding for article %s", article.id)

    return analysis_result


async def deep_analyze_article(article: NewsArticle, classification: AnalysisResult) -> str | None:
    text = f"Title: {article.title}\n\n{article.content or ''}"
    extract_prompt = _load_prompt("extract.yaml")

    try:
        result = await deep_analysis(text=text, system_prompt=extract_prompt)
        analysis = _parse_json(result, {})
        return analysis.get("impact_assessment", "")
    except Exception:
        logger.exception("Deep analysis failed for article %s", article.id)
        return None


def _parse_json(text: str, default):
    try:
        if isinstance(text, str):
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse JSON response: %s", text[:200])
        return default


def _safe_enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except ValueError:
        return default


def _extract_entities(classification: dict, companies: list) -> dict:
    entities = {"companies": companies}
    if "market_impact" in classification:
        entities["market_impact"] = classification["market_impact"]
    return entities


async def process_article_sequentially(article: NewsArticle, session: AsyncSession) -> None:
    # 1. Embed the article
    text_to_embed = f"{article.title}\n\n{article.content[:2000] if article.content else ''}"
    try:
        query_vector = await get_embedding(text_to_embed)
    except Exception:
        logger.exception("Failed to get embedding for article %s", article.id)
        query_vector = None

    # 2. Semantic deduplication check against recently processed articles
    if query_vector:
        try:
            similar_articles = search_embeddings_with_filter(query_vector, type_filter="article", limit=3)
            best_match = None
            for match in similar_articles:
                if match["id"] != article.id and match["score"] >= 0.90:
                    best_match = match
                    break
            
            if best_match:
                matched_id = best_match["id"]
                stmt = select(NewsArticle).where(NewsArticle.id == matched_id)
                matched_art = (await session.execute(stmt)).scalar_one_or_none()
                if matched_art:
                    logger.info("Semantic duplicate found. Article '%s' is syndicated content of '%s' (score: %.3f)", 
                                article.title[:50], matched_art.title[:50], best_match["score"])
                    
                    article.duplicate_of_id = matched_art.id
                    article.is_relevant = False
                    if matched_art.title_zh:
                        article.title_zh = matched_art.title_zh
                    
                    analysis_res = AnalysisResult(
                        article_id=article.id,
                        urgency=UrgencyEnum.LOW,
                        sentiment=SentimentEnum.NEUTRAL,
                        sentiment_score=0.0,
                        topics=[],
                        summary_en=article.title,
                        summary_zh=article.title_zh,
                        impact_assessment=f"Syndicated content of: {matched_art.title}",
                        llm_model="semantic_dedup",
                    )
                    session.add(analysis_res)
                    
                    try:
                        upsert_embedding(
                            point_id=article.id,
                            vector=query_vector,
                            payload={
                                "type": "article",
                                "title": article.title,
                                "source_name": article.source_name,
                                "published_at": article.published_at.isoformat() if article.published_at else None,
                                "language": article.language.value,
                            }
                        )
                    except Exception:
                        logger.exception("Failed to save article embedding for syndicated article %s", article.id)
                        
                    return
        except Exception:
            logger.exception("Failed semantic deduplication check for article %s", article.id)

    # 3. Search for similar active insights in vector store
    existing_insights_text = "None found."
    matching_insights_map = {}
    if query_vector:
        try:
            matches = search_embeddings_with_filter(query_vector, type_filter="insight", limit=3)
            if matches:
                insight_ids = [m["id"] for m in matches]
                from sqlalchemy.orm import selectinload
                stmt = select(Insight).where(Insight.id.in_(insight_ids)).options(selectinload(Insight.subject))
                insights = (await session.execute(stmt)).scalars().all()

                insights_list = []
                for ins in insights:
                    matching_insights_map[ins.id] = ins
                    # Get recent facts for context
                    facts_stmt = select(InsightFact).where(InsightFact.insight_id == ins.id).order_by(InsightFact.created_at.desc()).limit(5)
                    facts = (await session.execute(facts_stmt)).scalars().all()
                    bullets = "\n".join([f"  - {f.bullet_text_en}" for f in facts])
                    insights_list.append(
                        f"ID: {ins.id}\n"
                        f"Subject: {ins.subject.name} ({ins.subject.type.value})\n"
                        f"Dimension: {ins.dimension_name}\n"
                        f"Summary (EN): {ins.summary_en}\n"
                        f"Summary (ZH): {ins.summary_zh}\n"
                        f"Bullets:\n{bullets}"
                    )
                if insights_list:
                    existing_insights_text = "\n\n".join(insights_list)
        except Exception:
            logger.exception("Failed to query similar insights for article %s", article.id)

    # 4. Get glossary terms
    glossary_extension = await get_glossary_prompt_extension(text_to_embed, session)

    # 5. Construct prompt
    prompt_template = _load_prompt("sequential.txt")
    user_content = (
        "Here is the new article to analyze:\n"
        f"Title: {article.title}\n"
        f"Content: {article.content or ''}\n\n"
        "Here are the most relevant existing Insights from our Insight Vault:\n"
        f"{existing_insights_text}\n\n"
        f"{glossary_extension}"
    )

    # 6. Call LLM
    raw_response = await classify(text=user_content, system_prompt=prompt_template)
    decision = _parse_json(raw_response, {"action": "NO_CHANGE"})

    action = decision.get("action", "NO_CHANGE")

    translated_title = decision.get("translated_title")
    if translated_title and article.language == LanguageEnum.EN:
        article.title_zh = translated_title

    urgency_val = UrgencyEnum.MEDIUM
    sentiment_val = SentimentEnum.NEUTRAL
    summary_en_val = ""
    summary_zh_val = ""
    impact_val = ""

    if action == "UPDATE":
        insight_id = decision.get("insight_id")
        insight = matching_insights_map.get(insight_id)
        if not insight and insight_id:
            try:
                stmt = select(Insight).where(Insight.id == insight_id)
                insight = (await session.execute(stmt)).scalar_one_or_none()
            except Exception:
                insight = None

        if insight:
            # Update existing Insight
            insight.summary_en = decision.get("updated_summary_en", insight.summary_en)
            insight.summary_zh = decision.get("updated_summary_zh", insight.summary_zh)
            insight.urgency = _safe_enum(UrgencyEnum, decision.get("urgency"), insight.urgency)
            insight.sentiment = _safe_enum(SentimentEnum, decision.get("sentiment"), insight.sentiment)

            # Create fact bullet
            fact = InsightFact(
                insight_id=insight.id,
                bullet_text_en=decision.get("new_fact_bullet_en", ""),
                bullet_text_zh=decision.get("new_fact_bullet_zh", ""),
                source_article_id=article.id,
            )
            session.add(fact)

            urgency_val = insight.urgency
            sentiment_val = insight.sentiment
            summary_en_val = insight.summary_en
            summary_zh_val = insight.summary_zh
            impact_val = f"Updated existing insight: {insight.dimension_name}"

            # Update Insight Embedding
            try:
                insight_text = f"Subject: {insight.subject.name}\nDimension: {insight.dimension_name}\nSummary: {insight.summary_en}\n"
                insight_vector = await get_embedding(insight_text + "\n" + decision.get("new_fact_bullet_en", ""))
                upsert_embedding(
                    point_id=insight.id,
                    vector=insight_vector,
                    payload={
                        "type": "insight",
                        "subject": insight.subject.name,
                        "dimension_name": insight.dimension_name,
                        "summary_en": insight.summary_en,
                        "summary_zh": insight.summary_zh,
                        "tags": insight.tags,
                    }
                )
            except Exception:
                logger.exception("Failed to update embedding for insight %s", insight.id)
        else:
            action = "NEW"

    if action == "NEW":
        subject_name = decision.get("subject_name", "General")
        subject_type_str = decision.get("subject_type", "theme")
        subject_type = _safe_enum(SubjectTypeEnum, subject_type_str, SubjectTypeEnum.THEME)

        # Retrieve or create Subject
        stmt = select(Subject).where(Subject.name == subject_name)
        subject = (await session.execute(stmt)).scalar_one_or_none()
        if not subject:
            subject = Subject(
                name=subject_name,
                type=subject_type,
                tags=decision.get("tags", []),
            )
            session.add(subject)
            await session.flush()

        # Create Insight
        insight = Insight(
            subject_id=subject.id,
            dimension_name=decision.get("dimension_name", "General Insight"),
            summary_en=decision.get("summary_en", ""),
            summary_zh=decision.get("summary_zh", ""),
            urgency=_safe_enum(UrgencyEnum, decision.get("urgency"), UrgencyEnum.MEDIUM),
            sentiment=_safe_enum(SentimentEnum, decision.get("sentiment"), SentimentEnum.NEUTRAL),
            tags=decision.get("tags", []),
        )
        session.add(insight)
        await session.flush()

        # Create Fact
        fact = InsightFact(
            insight_id=insight.id,
            bullet_text_en=decision.get("new_fact_bullet_en", ""),
            bullet_text_zh=decision.get("new_fact_bullet_zh", ""),
            source_article_id=article.id,
        )
        session.add(fact)

        urgency_val = insight.urgency
        sentiment_val = insight.sentiment
        summary_en_val = insight.summary_en
        summary_zh_val = insight.summary_zh
        impact_val = f"Created new insight: {insight.dimension_name}"

        # Save Insight Embedding
        try:
            insight_text = f"Subject: {subject.name}\nDimension: {insight.dimension_name}\nSummary: {insight.summary_en}\n"
            insight_vector = await get_embedding(insight_text + "\n" + decision.get("new_fact_bullet_en", ""))
            upsert_embedding(
                point_id=insight.id,
                vector=insight_vector,
                payload={
                    "type": "insight",
                    "subject": subject.name,
                    "dimension_name": insight.dimension_name,
                    "summary_en": insight.summary_en,
                    "summary_zh": insight.summary_zh,
                    "tags": insight.tags,
                }
            )
        except Exception:
            logger.exception("Failed to create embedding for new insight %s", insight.id)

    # Save raw article embedding (Scenario B)
    if query_vector:
        try:
            upsert_embedding(
                point_id=article.id,
                vector=query_vector,
                payload={
                    "type": "article",
                    "title": article.title,
                    "source_name": article.source_name,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                    "language": article.language.value,
                }
            )
        except Exception:
            logger.exception("Failed to save article embedding for %s", article.id)

    # Register glossary terms
    detected = decision.get("detected_entities", {})
    if detected:
        await register_detected_entities(detected, session)

    # Create AnalysisResult record to link with article
    analysis_res = AnalysisResult(
        article_id=article.id,
        urgency=urgency_val,
        sentiment=sentiment_val,
        sentiment_score=float(decision.get("sentiment_score", 0.0)) if decision.get("sentiment_score") else 0.0,
        topics=decision.get("tags", []),
        summary_en=summary_en_val or article.title,
        summary_zh=summary_zh_val or article.title_zh,
        impact_assessment=impact_val or "No change in existing insights.",
        llm_model="sequential_pipeline",
    )
    session.add(analysis_res)
    
    # Clear heavy fields to save space
    article.content = None
    article.summary = None
    
    logger.info("Processed article '%s', Action: %s", article.title[:50], action)