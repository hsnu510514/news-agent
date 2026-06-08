from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.models.schema import EntityGlossary
from src.storage.database import get_session

router = APIRouter()


class GlossaryItemCreate(BaseModel):
    term_en: str
    term_zh: str
    type: str = "company"
    is_verified: bool = True


@router.get("")
async def list_glossary(
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(EntityGlossary).order_by(EntityGlossary.term_en)
    rows = (await session.execute(stmt)).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "term_en": r.term_en,
                "term_zh": r.term_zh,
                "type": r.type,
                "is_verified": r.is_verified,
            }
            for r in rows
        ]
    }


@router.post("")
async def create_glossary_item(
    item: GlossaryItemCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Check if duplicate exists
    stmt = select(EntityGlossary).where(
        (EntityGlossary.term_en == item.term_en) | (EntityGlossary.term_zh == item.term_zh)
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing:
        # Update it instead of duplicating
        existing.term_en = item.term_en
        existing.term_zh = item.term_zh
        existing.type = item.type
        existing.is_verified = item.is_verified
        await session.commit()
        return {"status": "updated", "id": existing.id}

    db_item = EntityGlossary(
        term_en=item.term_en,
        term_zh=item.term_zh,
        type=item.type,
        is_verified=item.is_verified,
    )
    session.add(db_item)
    await session.commit()
    return {"status": "created", "id": db_item.id}


@router.post("/{item_id}/verify")
async def verify_glossary_item(
    item_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(EntityGlossary).where(EntityGlossary.id == item_id)
    item = (await session.execute(stmt)).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Glossary item not found")

    item.is_verified = True
    await session.commit()
    return {"status": "verified"}


class GlossaryItemUpdate(BaseModel):
    term_en: str
    term_zh: str
    type: str = "company"
    is_verified: bool = True


@router.put("/{item_id}")
async def update_glossary_item(
    item_id: str,
    item: GlossaryItemUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(EntityGlossary).where(EntityGlossary.id == item_id)
    db_item = (await session.execute(stmt)).scalar_one_or_none()

    if not db_item:
        raise HTTPException(status_code=404, detail="Glossary item not found")

    db_item.term_en = item.term_en
    db_item.term_zh = item.term_zh
    db_item.type = item.type
    db_item.is_verified = item.is_verified
    await session.commit()
    return {"status": "updated"}

