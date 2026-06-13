from __future__ import annotations

import logging
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from src.core.llm import deep_analysis
from src.models.schema import Insight, InsightFact, DailyBriefing
from src.storage.database import async_session_factory

logger = logging.getLogger("news-agent")


async def generate_daily_briefing() -> DailyBriefing | None:
    """
    Cron-compatible task to aggregate all insight updates in the last 24 hours
    and synthesize a bilingual briefing card.
    """
    logger.info("Starting Daily Briefing generation...")
    async with async_session_factory() as session:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)

        # Retrieve all insights updated in the last 24 hours
        from sqlalchemy.orm import selectinload
        stmt = select(Insight).where(Insight.last_updated_at >= cutoff).options(selectinload(Insight.subject))
        insights = (await session.execute(stmt)).scalars().all()

        if not insights:
            logger.info("No insights updated in the last 24 hours. Creating empty placeholder briefing.")
            briefing = DailyBriefing(
                summary_en="No major financial or macroeconomic policy updates were recorded in the last 24 hours.",
                summary_zh="过去24小时内未记录重大财务或宏观经济政策更新。",
                key_takeaways_en=["Quiet market day with no major updates."],
                key_takeaways_zh=["市场日平静，无重大更新。"],
            )
            session.add(briefing)
            await session.commit()
            return briefing

        # Format updates for LLM prompt
        updates_text_list = []
        for ins in insights:
            facts_stmt = select(InsightFact).where(InsightFact.insight_id == ins.id).order_by(InsightFact.created_at.desc()).limit(5)
            facts = (await session.execute(facts_stmt)).scalars().all()
            bullets = "\n".join([f"  - {f.bullet_text_en}" for f in facts])
            updates_text_list.append(
                f"Subject: {ins.subject.name} ({ins.subject.type.value})\n"
                f"Dimension: {ins.dimension_name}\n"
                f"Urgency: {ins.urgency.value}, Sentiment: {ins.sentiment.value}\n"
                f"Summary: {ins.summary_en}\n"
                f"Recent Facts:\n{bullets}"
            )
        updates_text = "\n\n".join(updates_text_list)

        system_prompt = (
            "You are an expert investment analyst synthesizing a Daily Briefing.\n"
            "Synthesize this information into a high-level bilingual Daily Briefing. "
            "Group updates by significance, separating macro themes from corporate ones. "
            "Output your response strictly as a JSON object with this format:\n"
            "{\n"
            "  \"summary_en\": \"A cohesive, newsletter-style summary of the day's major events in English.\",\n"
            "  \"summary_zh\": \"A cohesive, newsletter-style summary of the day's major events in Chinese.\",\n"
            "  \"key_takeaways_en\": [\"3-5 key high-impact takeaways in English\"],\n"
            "  \"key_takeaways_zh\": [\"3-5 key high-impact takeaways in Chinese\"]\n"
            "}\n"
        )
        user_content = (
            "Here are the updates from our Insight Vault over the previous 24 hours:\n\n"
            f"{updates_text}"
        )

        try:
            raw_response = await deep_analysis(text=user_content, system_prompt=system_prompt, priority=0)
            clean_response = raw_response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            data = json.loads(clean_response)

            briefing = DailyBriefing(
                summary_en=data.get("summary_en", ""),
                summary_zh=data.get("summary_zh", ""),
                key_takeaways_en=data.get("key_takeaways_en", []),
                key_takeaways_zh=data.get("key_takeaways_zh", []),
            )
            session.add(briefing)
            await session.commit()
            logger.info("Successfully generated and saved Daily Briefing.")
            return briefing
        except Exception:
            logger.exception("Failed to synthesize Daily Briefing.")
            return None
