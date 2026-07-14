from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import AbilityDimension, MasteryAlgorithm, MasteryStatus
from app.models import KnowledgePoint, MasteryResult, StudentProfile
from app.schemas.teacher import (
    AttentionStudent,
    DimensionStatistic,
    KnowledgeStatistic,
    StatusDistribution,
    TeacherOverview,
)
from app.services.diagnosis import recompute_bkt_mastery, recompute_rule_mastery


def build_overview(
    db: Session,
    *,
    student_ids: list[int],
    attention_student_ids: set[int],
    algorithm: MasteryAlgorithm,
) -> TeacherOverview:
    if not student_ids:
        return TeacherOverview(
            algorithm=algorithm,
            student_count=0,
            average_mastery=0,
            dimensions=[],
            knowledge_points=[],
            weak_top5=[],
            attention_students=[],
        )
    updater = recompute_rule_mastery if algorithm == MasteryAlgorithm.RULE else recompute_bkt_mastery
    updater(db, student_ids)

    rows = db.execute(
        select(MasteryResult, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == MasteryResult.knowledge_point_id)
        .where(
            MasteryResult.student_id.in_(student_ids),
            MasteryResult.algorithm == algorithm,
            KnowledgePoint.is_active.is_(True),
        )
    ).all()
    by_point: dict[int, list[MasteryResult]] = defaultdict(list)
    point_map: dict[int, KnowledgePoint] = {}
    dimension_scores: dict[AbilityDimension, list[float]] = defaultdict(list)
    student_scores: dict[int, list[MasteryResult]] = defaultdict(list)
    for result, point in rows:
        by_point[point.id].append(result)
        point_map[point.id] = point
        dimension_scores[point.dimension].append(result.score)
        student_scores[result.student_id].append(result)

    knowledge_statistics: list[KnowledgeStatistic] = []
    for point_id, results in by_point.items():
        scores = [item.score for item in results]
        counts = {status: 0 for status in MasteryStatus}
        for item in results:
            counts[item.status] += 1
        knowledge_statistics.append(
            KnowledgeStatistic(
                knowledge_point_id=point_id,
                name=point_map[point_id].name,
                average=round(sum(scores) / len(scores), 6),
                minimum=round(min(scores), 6),
                maximum=round(max(scores), 6),
                distribution=StatusDistribution(
                    unknown=counts[MasteryStatus.UNKNOWN],
                    weak=counts[MasteryStatus.WEAK],
                    learning=counts[MasteryStatus.LEARNING],
                    mastered=counts[MasteryStatus.MASTERED],
                ),
            )
        )
    knowledge_statistics.sort(key=lambda item: item.knowledge_point_id)

    students = {
        item.id: item
        for item in db.scalars(
            select(StudentProfile)
            .where(StudentProfile.id.in_(attention_student_ids))
            .options(selectinload(StudentProfile.user), selectinload(StudentProfile.classroom))
        )
    }
    attention: list[AttentionStudent] = []
    for student_id in attention_student_ids:
        results = student_scores.get(student_id, [])
        if not results or student_id not in students:
            continue
        average = sum(item.score for item in results) / len(results)
        weak_count = sum(item.status in (MasteryStatus.WEAK, MasteryStatus.UNKNOWN) for item in results)
        if average < 0.5 or weak_count >= 6:
            student = students[student_id]
            attention.append(
                AttentionStudent(
                    student_id=student.id,
                    student_no=student.student_no,
                    display_name=student.user.display_name,
                    classroom_name=student.classroom.name,
                    average=round(average, 6),
                    weak_count=weak_count,
                )
            )
    attention.sort(key=lambda item: (item.average, -item.weak_count))
    all_scores = [result.score for result, _ in rows]
    return TeacherOverview(
        algorithm=algorithm,
        student_count=len(student_ids),
        average_mastery=round(sum(all_scores) / len(all_scores), 6),
        dimensions=[
            DimensionStatistic(dimension=dimension, average=round(sum(scores) / len(scores), 6))
            for dimension, scores in sorted(dimension_scores.items(), key=lambda item: item[0].value)
        ],
        knowledge_points=knowledge_statistics,
        weak_top5=sorted(knowledge_statistics, key=lambda item: item.average)[:5],
        attention_students=attention,
    )

