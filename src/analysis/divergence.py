import os
from sqlalchemy import select
from src.models.schema import Subject, Insight, PotentialDuplicate
from rapidfuzz.distance.Levenshtein import normalized_similarity

async def scan_for_duplicates(session) -> dict:
    subject_threshold = float(os.getenv("SUBJECT_SIMILARITY_THRESHOLD", "0.70"))
    insight_threshold = float(os.getenv("INSIGHT_SIMILARITY_THRESHOLD", "0.80"))

    # Load existing duplicate pairs to avoid re-inserting
    existing_stmt = select(PotentialDuplicate.entity_type, PotentialDuplicate.id1, PotentialDuplicate.id2)
    existing_rows = (await session.execute(existing_stmt)).all()
    existing_pairs = {(r[0], r[1], r[2]) for r in existing_rows}

    # 1. Scan Subjects
    subjects_stmt = select(Subject)
    subjects = (await session.execute(subjects_stmt)).scalars().all()
    
    by_type = {}
    for s in subjects:
        by_type.setdefault(s.type, []).append(s)

    subjects_duplicates_found = 0
    for stype, sublist in by_type.items():
        n = len(sublist)
        for i in range(n):
            for j in range(i + 1, n):
                s1 = sublist[i]
                s2 = sublist[j]
                sim = normalized_similarity(s1.name, s2.name)
                if sim >= subject_threshold:
                    subjects_duplicates_found += 1
                    id1, id2 = sorted([s1.id, s2.id])
                    pair = ("subject", id1, id2)
                    if pair not in existing_pairs:
                        dup = PotentialDuplicate(
                            entity_type="subject",
                            id1=id1,
                            id2=id2,
                            similarity=round(sim, 2),
                            status="pending"
                        )
                        session.add(dup)
                        existing_pairs.add(pair)

    # 2. Scan Insights
    insights_stmt = select(Insight)
    insights = (await session.execute(insights_stmt)).scalars().all()

    by_subject = {}
    for ins in insights:
        by_subject.setdefault(ins.subject_id, []).append(ins)

    insights_duplicates_found = 0
    for sub_id, ins_list in by_subject.items():
        n = len(ins_list)
        for i in range(n):
            for j in range(i + 1, n):
                ins1 = ins_list[i]
                ins2 = ins_list[j]
                sim = normalized_similarity(ins1.summary_en, ins2.summary_en)
                if sim >= insight_threshold:
                    insights_duplicates_found += 1
                    id1, id2 = sorted([ins1.id, ins2.id])
                    pair = ("insight", id1, id2)
                    if pair not in existing_pairs:
                        dup = PotentialDuplicate(
                            entity_type="insight",
                            id1=id1,
                            id2=id2,
                            similarity=round(sim, 2),
                            status="pending"
                        )
                        session.add(dup)
                        existing_pairs.add(pair)

    await session.commit()

    return {
        "subjects_scanned": len(subjects),
        "subjects_duplicates_found": subjects_duplicates_found,
        "insights_scanned": len(insights),
        "insights_duplicates_found": insights_duplicates_found
    }
