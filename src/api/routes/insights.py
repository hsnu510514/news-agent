from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func, update, or_
from sqlalchemy.orm import selectinload, aliased
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.models.schema import Insight, Subject, InsightFact, UrgencyEnum, SubjectTypeEnum, PotentialDuplicate
from src.storage.database import get_session



router = APIRouter()


@router.get("/top-tags")
async def list_top_tags(
    subject_type: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    tag_func = func.jsonb_array_elements_text(Subject.tags).label("tag")
    stmt = select(tag_func, func.count().label("count"))
    
    if subject_type:
        try:
            st_enum = SubjectTypeEnum(subject_type.lower())
            stmt = stmt.where(Subject.type == st_enum)
        except ValueError:
            pass
            
    stmt = stmt.where(Subject.tags.is_not(None)).group_by("tag").order_by(desc("count")).limit(15)
    
    rows = (await session.execute(stmt)).all()
    tags = [r[0] for r in rows if r[0]]
    return {"tags": tags}


@router.get("")
async def list_insights(
    tag: str | None = None,
    subject_id: str | None = None,
    subject_type: str | None = None,
    q: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from sqlalchemy import cast, String
    stmt = select(Insight).options(
        selectinload(Insight.subject),
        selectinload(Insight.facts).selectinload(InsightFact.source_article)
    ).order_by(desc(Insight.last_updated_at))

    joined_subject = False

    if subject_type:
        try:
            st_enum = SubjectTypeEnum(subject_type.lower())
            stmt = stmt.join(Subject)
            stmt = stmt.where(Subject.type == st_enum)
            joined_subject = True
        except ValueError:
            pass

    if q:
        if not joined_subject:
            stmt = stmt.join(Subject)
            joined_subject = True
        q_filter = f"%{q}%"
        stmt = stmt.where(
            (Subject.name.ilike(q_filter)) |
            (Insight.dimension_name.ilike(q_filter)) |
            (cast(Insight.tags, String).ilike(q_filter))
        )

    if tag:
        # Check if tag is inside JSONB array tags
        stmt = stmt.where(Insight.tags.contains([tag]))
    if subject_id:
        stmt = stmt.where(Insight.subject_id == subject_id)

    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "dimension_name": r.dimension_name,
                "summary_en": r.summary_en,
                "summary_zh": r.summary_zh,
                "urgency": r.urgency.value,
                "sentiment": r.sentiment.value,
                "tags": r.tags,
                "last_updated_at": r.last_updated_at.isoformat(),
                "subject": {
                    "id": r.subject.id,
                    "name": r.subject.name,
                    "type": r.subject.type.value,
                    "tags": r.subject.tags,
                },
                "facts": [
                    {
                        "id": f.id,
                        "bullet_text_en": f.bullet_text_en,
                        "bullet_text_zh": f.bullet_text_zh,
                        "created_at": f.created_at.isoformat(),
                        "source_article": {
                            "id": f.source_article.id,
                            "title": f.source_article.title,
                            "title_zh": f.source_article.title_zh,
                            "url": f.source_article.url,
                            "source_name": f.source_article.source_name,
                        } if f.source_article else None,
                    }
                    for f in sorted(r.facts, key=lambda x: x.created_at, reverse=True)
                ],
            }
            for r in rows
        ]
    }


@router.get("/alerts")
async def list_emergency_alerts(
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Alerts are Insights where urgency is 'flash'
    stmt = select(Insight).options(
        selectinload(Insight.subject),
        selectinload(Insight.facts).selectinload(InsightFact.source_article)
    ).where(Insight.urgency == UrgencyEnum.FLASH).order_by(desc(Insight.last_updated_at))

    rows = (await session.execute(stmt)).scalars().all()

    return {
        "alerts": [
            {
                "id": r.id,
                "subject_name": r.subject.name,
                "dimension_name": r.dimension_name,
                "summary_en": r.summary_en,
                "summary_zh": r.summary_zh,
                "last_updated_at": r.last_updated_at.isoformat(),
                "recent_fact": r.facts[0].bullet_text_en if r.facts else None,
                "recent_fact_zh": r.facts[0].bullet_text_zh if r.facts else None,
            }
            for r in rows
        ]
    }


def levenshtein_ratio(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    s1 = s1.strip().lower()
    s2 = s2.strip().lower()
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
    distance = dp[m][n]
    max_len = max(m, n)
    return (max_len - distance) / max_len if max_len > 0 else 0.0


@router.get("/divergence")
async def list_divergence(
    session: AsyncSession = Depends(get_session),
) -> dict:
    Subj1 = aliased(Subject, name="s1")
    Subj2 = aliased(Subject, name="s2")

    subjects_stmt = (
        select(PotentialDuplicate, Subj1, Subj2)
        .join(Subj1, PotentialDuplicate.id1 == Subj1.id)
        .join(Subj2, PotentialDuplicate.id2 == Subj2.id)
        .where(
            PotentialDuplicate.entity_type == "subject",
            PotentialDuplicate.status == "pending"
        )
    )
    subjects_rows = (await session.execute(subjects_stmt)).all()

    duplicate_subjects = [
        {
            "id1": r[0].id1,
            "name1": r[1].name,
            "id2": r[0].id2,
            "name2": r[2].name,
            "type": r[1].type.value,
            "similarity": r[0].similarity
        }
        for r in subjects_rows
    ]

    Ins1 = aliased(Insight, name="i1")
    Ins2 = aliased(Insight, name="i2")

    insights_stmt = (
        select(PotentialDuplicate, Ins1, Ins2, Subject)
        .join(Ins1, PotentialDuplicate.id1 == Ins1.id)
        .join(Ins2, PotentialDuplicate.id2 == Ins2.id)
        .join(Subject, Ins1.subject_id == Subject.id)
        .where(
            PotentialDuplicate.entity_type == "insight",
            PotentialDuplicate.status == "pending"
        )
    )
    insights_rows = (await session.execute(insights_stmt)).all()

    duplicate_insights = [
        {
            "subject_name": r[3].name,
            "id1": r[0].id1,
            "dim1": r[1].dimension_name,
            "summary1": r[1].summary_en,
            "id2": r[0].id2,
            "dim2": r[2].dimension_name,
            "summary2": r[2].summary_en,
            "similarity": r[0].similarity
        }
        for r in insights_rows
    ]

    return {
        "subjects": duplicate_subjects,
        "insights": duplicate_insights
    }


class DivergenceResolveRequest(BaseModel):
    entity_type: str  # "subject" or "insight"
    id1: str
    id2: str
    action: str  # "ignore" or "merge"
    primary_id: str | None = None


@router.post("/divergence/resolve")
async def resolve_divergence(
    req: DivergenceResolveRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    from fastapi import HTTPException
    
    id1, id2 = sorted([req.id1, req.id2])
    stmt = (
        select(PotentialDuplicate)
        .where(
            PotentialDuplicate.entity_type == req.entity_type,
            PotentialDuplicate.id1 == id1,
            PotentialDuplicate.id2 == id2
        )
    )
    dup = (await session.execute(stmt)).scalar_one_or_none()
    if not dup:
        raise HTTPException(status_code=404, detail="Potential duplicate relation not found")

    if req.action == "ignore":
        dup.status = "ignored"
        await session.commit()
        return {"status": "resolved", "action": "ignored"}

    elif req.action == "merge":
        if not req.primary_id:
            raise HTTPException(status_code=400, detail="primary_id is required for merge action")

        primary_id = req.primary_id
        secondary_id = id2 if primary_id == id1 else id1

        if req.entity_type == "subject":
            subj_prim = await session.get(Subject, primary_id)
            subj_sec = await session.get(Subject, secondary_id)
            if not subj_prim or not subj_sec:
                raise HTTPException(status_code=404, detail="Subject not found")

            # 1. Reparent all insights under the secondary subject to the primary subject
            update_insights_stmt = (
                update(Insight)
                .where(Insight.subject_id == secondary_id)
                .values(subject_id=primary_id)
            )
            await session.execute(update_insights_stmt)

            # 2. Merge tags list
            tags_prim = list(subj_prim.tags or [])
            tags_sec = list(subj_sec.tags or [])
            merged_tags = list(set(tags_prim + tags_sec))
            subj_prim.tags = merged_tags

            # 3. Delete secondary subject
            await session.delete(subj_sec)

        elif req.entity_type == "insight":
            ins_prim = await session.get(Insight, primary_id)
            ins_sec = await session.get(Insight, secondary_id)
            if not ins_prim or not ins_sec:
                raise HTTPException(status_code=404, detail="Insight not found")

            # 1. Reparent all facts under secondary insight to primary insight
            update_facts_stmt = (
                update(InsightFact)
                .where(InsightFact.insight_id == secondary_id)
                .values(insight_id=primary_id)
            )
            await session.execute(update_facts_stmt)

            # 2. Merge tags list
            tags_prim = list(ins_prim.tags or [])
            tags_sec = list(ins_sec.tags or [])
            merged_tags = list(set(tags_prim + tags_sec))
            ins_prim.tags = merged_tags

            # 3. Delete secondary insight
            await session.delete(ins_sec)

        # 4. Cascading cleanup: update any other pending duplicate records referencing secondary_id to "merged"
        cascade_stmt = (
            update(PotentialDuplicate)
            .where(
                PotentialDuplicate.entity_type == req.entity_type,
                PotentialDuplicate.status == "pending",
                or_(PotentialDuplicate.id1 == secondary_id, PotentialDuplicate.id2 == secondary_id)
            )
            .values(status="merged")
        )
        await session.execute(cascade_stmt)

        # 5. Mark current duplicate record as merged
        dup.status = "merged"
        await session.commit()
        return {"status": "resolved", "action": "merged"}

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


