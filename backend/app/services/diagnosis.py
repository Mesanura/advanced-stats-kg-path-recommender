from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, MasteryStatus
from app.models import ExerciseAttempt, KnowledgePoint, KnowledgeVisit, MasteryResult, StudentProfile


def mastery_status(
    score: float,
    evidence_count: int,
    *,
    weak_threshold: float = 0.5,
    mastery_threshold: float = 0.7,
) -> MasteryStatus:
    if evidence_count == 0:
        return MasteryStatus.UNKNOWN
    if score < weak_threshold:
        return MasteryStatus.WEAK
    if score < mastery_threshold:
        return MasteryStatus.LEARNING
    return MasteryStatus.MASTERED


def calculate_rule_score(
    *,
    correct: int,
    attempts: int,
    visit_count: int,
    duration_seconds: int,
) -> tuple[float, int]:
    correctness = (correct + 1) / (attempts + 2)
    frequency = min(visit_count / 3, 1.0)
    duration = min(duration_seconds / 1800, 1.0)
    score = 0.60 * correctness + 0.20 * frequency + 0.20 * duration
    return round(float(score), 6), attempts + visit_count


def recompute_rule_mastery(
    db: Session,
    student_ids: Iterable[int] | None = None,
) -> int:
    selected_ids = list(student_ids) if student_ids is not None else list(
        db.scalars(select(StudentProfile.id))
    )
    if not selected_ids:
        return 0

    exercise_rows = db.execute(
        select(
            ExerciseAttempt.student_id,
            ExerciseAttempt.knowledge_point_id,
            func.count(ExerciseAttempt.id),
            func.sum(func.cast(ExerciseAttempt.is_correct, type_=ExerciseAttempt.id.type)),
        )
        .where(ExerciseAttempt.student_id.in_(selected_ids))
        .group_by(ExerciseAttempt.student_id, ExerciseAttempt.knowledge_point_id)
    )
    exercise_stats = {
        (student_id, point_id): (int(attempts), int(correct or 0))
        for student_id, point_id, attempts, correct in exercise_rows
    }
    visit_rows = db.execute(
        select(
            KnowledgeVisit.student_id,
            KnowledgeVisit.knowledge_point_id,
            func.count(KnowledgeVisit.id),
            func.sum(KnowledgeVisit.duration_seconds),
        )
        .where(KnowledgeVisit.student_id.in_(selected_ids))
        .group_by(KnowledgeVisit.student_id, KnowledgeVisit.knowledge_point_id)
    )
    visit_stats = {
        (student_id, point_id): (int(count), int(duration or 0))
        for student_id, point_id, count, duration in visit_rows
    }
    points = list(db.scalars(select(KnowledgePoint.id).where(KnowledgePoint.is_active.is_(True))))
    existing = {
        (item.student_id, item.knowledge_point_id): item
        for item in db.scalars(
            select(MasteryResult).where(
                MasteryResult.student_id.in_(selected_ids),
                MasteryResult.algorithm == MasteryAlgorithm.RULE,
            )
        )
    }
    calculated_at = datetime.now(UTC)
    changed = 0
    for student_id in selected_ids:
        for point_id in points:
            attempts, correct = exercise_stats.get((student_id, point_id), (0, 0))
            visit_count, duration = visit_stats.get((student_id, point_id), (0, 0))
            score, evidence_count = calculate_rule_score(
                correct=correct,
                attempts=attempts,
                visit_count=visit_count,
                duration_seconds=duration,
            )
            result = existing.get((student_id, point_id))
            if result is None:
                result = MasteryResult(
                    student_id=student_id,
                    knowledge_point_id=point_id,
                    algorithm=MasteryAlgorithm.RULE,
                )
                db.add(result)
            result.score = score
            result.status = mastery_status(score, evidence_count)
            result.evidence_count = evidence_count
            result.calculated_at = calculated_at
            changed += 1
    db.commit()
    return changed

