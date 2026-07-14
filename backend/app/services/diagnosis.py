from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, precision_recall_fscore_support

from app.enums import MasteryAlgorithm, MasteryStatus
from app.models import (
    ExerciseAttempt,
    KnowledgePoint,
    KnowledgeVisit,
    LatentMastery,
    MasteryResult,
    StudentProfile,
)


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


def calculate_bkt_score(
    outcomes: Iterable[bool],
    *,
    p_l0: float = 0.20,
    p_t: float = 0.15,
    p_s: float = 0.10,
    p_g: float = 0.20,
) -> tuple[float, int]:
    mastery = p_l0
    count = 0
    for is_correct in outcomes:
        if is_correct:
            probability = mastery * (1 - p_s) + (1 - mastery) * p_g
            posterior = mastery * (1 - p_s) / probability
        else:
            probability = mastery * p_s + (1 - mastery) * (1 - p_g)
            posterior = mastery * p_s / probability
        mastery = posterior + (1 - posterior) * p_t
        count += 1
    return round(float(np_clip(mastery)), 6), count


def np_clip(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def recompute_bkt_mastery(
    db: Session,
    student_ids: Iterable[int] | None = None,
) -> int:
    selected_ids = list(student_ids) if student_ids is not None else list(
        db.scalars(select(StudentProfile.id))
    )
    if not selected_ids:
        return 0
    attempts = db.execute(
        select(
            ExerciseAttempt.student_id,
            ExerciseAttempt.knowledge_point_id,
            ExerciseAttempt.is_correct,
        )
        .where(ExerciseAttempt.student_id.in_(selected_ids))
        .order_by(
            ExerciseAttempt.student_id,
            ExerciseAttempt.knowledge_point_id,
            ExerciseAttempt.attempted_at,
            ExerciseAttempt.id,
        )
    )
    sequences: dict[tuple[int, int], list[bool]] = {}
    for student_id, point_id, is_correct in attempts:
        sequences.setdefault((student_id, point_id), []).append(bool(is_correct))

    point_ids = list(db.scalars(select(KnowledgePoint.id).where(KnowledgePoint.is_active.is_(True))))
    existing = {
        (item.student_id, item.knowledge_point_id): item
        for item in db.scalars(
            select(MasteryResult).where(
                MasteryResult.student_id.in_(selected_ids),
                MasteryResult.algorithm == MasteryAlgorithm.BKT,
            )
        )
    }
    calculated_at = datetime.now(UTC)
    changed = 0
    for student_id in selected_ids:
        for point_id in point_ids:
            score, evidence_count = calculate_bkt_score(sequences.get((student_id, point_id), []))
            result = existing.get((student_id, point_id))
            if result is None:
                result = MasteryResult(
                    student_id=student_id,
                    knowledge_point_id=point_id,
                    algorithm=MasteryAlgorithm.BKT,
                )
                db.add(result)
            result.score = score
            result.status = mastery_status(score, evidence_count)
            result.evidence_count = evidence_count
            result.calculated_at = calculated_at
            changed += 1
    db.commit()
    return changed


def evaluate_algorithms(db: Session) -> list[dict[str, float | str | int]]:
    latent = {
        (row.student_id, row.knowledge_point_id): row.score
        for row in db.scalars(select(LatentMastery))
    }
    evaluations: list[dict[str, float | str | int]] = []
    for algorithm in MasteryAlgorithm:
        results = list(
            db.scalars(select(MasteryResult).where(MasteryResult.algorithm == algorithm))
        )
        pairs = [
            (latent[(item.student_id, item.knowledge_point_id)], item.score)
            for item in results
            if (item.student_id, item.knowledge_point_id) in latent
        ]
        if not pairs:
            continue
        actual, predicted = zip(*pairs, strict=True)
        actual_weak = [value < 0.5 for value in actual]
        predicted_weak = [value < 0.5 for value in predicted]
        precision, recall, f1, _ = precision_recall_fscore_support(
            actual_weak,
            predicted_weak,
            average="binary",
            zero_division=0,
        )
        correlation = spearmanr(actual, predicted).statistic
        evaluations.append(
            {
                "algorithm": algorithm.value,
                "sample_size": len(pairs),
                "mae": round(float(mean_absolute_error(actual, predicted)), 6),
                "rmse": round(float(mean_squared_error(actual, predicted) ** 0.5), 6),
                "spearman": round(float(correlation), 6),
                "weak_precision": round(float(precision), 6),
                "weak_recall": round(float(recall), 6),
                "weak_f1": round(float(f1), 6),
            }
        )
    return evaluations
