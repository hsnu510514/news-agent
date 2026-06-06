from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.schema import EntityGlossary

logger = logging.getLogger("news-agent")


async def get_glossary_prompt_extension(text: str, session: AsyncSession) -> str:
    """
    Scans the given text for known glossary terms and returns a prompt instruction
    forcing the LLM to use the correct translations.
    """
    try:
        # Fetch all glossary terms
        # For simplicity and small database sizes, we fetch everything.
        # This is extremely cheap since the glossary typically contains 100-1000 terms.
        stmt = select(EntityGlossary)
        result = await session.execute(stmt)
        terms = result.scalars().all()

        matched_mappings = []
        lower_text = text.lower()

        for term in terms:
            # Match if English term is in text (case insensitive) or Chinese term is in text
            if term.term_en.lower() in lower_text or term.term_zh in text:
                matched_mappings.append(f"- {term.term_en} <-> {term.term_zh}")

        if matched_mappings:
            prompt_block = (
                "\nUse the following official translation glossary for names, companies, and technical terms to ensure consistency:\n"
                + "\n".join(matched_mappings)
                + "\n"
            )
            return prompt_block
    except Exception as e:
        logger.warning("Failed to construct glossary prompt extension: %s", e)

    return ""


async def register_detected_entities(entities: dict, session: AsyncSession) -> None:
    """
    Accepts a dictionary of entities detected by the LLM (e.g. {"companies": ["NVDA", "Apple"], "institutions": ["Fed"]})
    and inserts any new ones into the glossary as unverified.
    """
    try:
        # We can extract the companies/tickers and other key terms
        companies = entities.get("companies", [])
        institutions = entities.get("institutions", [])
        themes = entities.get("themes", [])

        # Flatten list of items to register
        items_to_register = []
        for c in companies:
            items_to_register.append((c, c, "company"))
        for inst in institutions:
            items_to_register.append((inst, inst, "institution"))
        for t in themes:
            items_to_register.append((t, t, "theme"))

        for term_en, term_zh, term_type in items_to_register:
            if not term_en:
                continue
            # Check if term already exists
            stmt = select(EntityGlossary).where(
                (EntityGlossary.term_en == term_en) | (EntityGlossary.term_zh == term_zh)
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                new_term = EntityGlossary(
                    term_en=term_en,
                    term_zh=term_zh,
                    type=term_type,
                    is_verified=False,
                )
                session.add(new_term)
        await session.flush()
    except Exception as e:
        logger.warning("Failed to register new glossary terms: %s", e)
