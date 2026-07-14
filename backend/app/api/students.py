from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.api.diagnosis import build_diagnosis, student_or_404
from app.api.recommendations import path_to_read
from app.db import get_db
from app.enums import MasteryAlgorithm, PathState, Role
from app.models import (
    ExerciseAttempt,
    KnowledgePoint,
    KnowledgeVisit,
    LearningPath,
    MasteryResult,
    RecommendationConfig,
    User,
    VideoProgress,
)
from app.schemas.behavior import BehaviorFeedback, ExerciseCreate, VideoProgressCreate, VisitCreate
from app.schemas.knowledge import KnowledgePointRead
from app.schemas.student import DimensionMastery, StudentDashboard
from app.services.diagnosis import recompute_bkt_mastery, recompute_rule_mastery

router = APIRouter(prefix="/students", tags=["students"])


def current_student(user: User):
    if user.student_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学生档案不存在")
    return user.student_profile


def point_or_404(db: Session, point_id: int) -> KnowledgePoint:
    point = db.get(KnowledgePoint, point_id)
    if point is None or not point.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识点不存在")
    return point


def finish_feedback(
    db: Session,
    *,
    student_id: int,
    point_id: int,
    message: str,
) -> BehaviorFeedback:
    config = db.get(RecommendationConfig, 1)
    algorithm = config.diagnostic_algorithm if config else MasteryAlgorithm.BKT
    result = db.scalar(
        select(MasteryResult).where(
            MasteryResult.student_id == student_id,
            MasteryResult.knowledge_point_id == point_id,
            MasteryResult.algorithm == algorithm,
        )
    )
    assert result is not None
    paths = list(
        db.scalars(
            select(LearningPath).where(
                LearningPath.student_id == student_id,
                LearningPath.state == PathState.CURRENT,
            )
        )
    )
    for path in paths:
        path.state = PathState.STALE
    db.commit()
    return BehaviorFeedback(
        message=message,
        knowledge_point_id=point_id,
        mastery_score=result.score,
        mastery_status=result.status,
        paths_marked_stale=len(paths),
    )


@router.get("/me/dashboard", response_model=StudentDashboard)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> StudentDashboard:
    if user.student_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学生档案不存在")
    student = student_or_404(db, user.student_profile.id)
    config = db.get(RecommendationConfig, 1)
    algorithm = config.diagnostic_algorithm if config else MasteryAlgorithm.BKT
    diagnosis = build_diagnosis(db, student, algorithm)
    dimensions: dict[object, list[float]] = defaultdict(list)
    for item in diagnosis.items:
        dimensions[item.dimension].append(item.score)
    paths = db.scalars(
        select(LearningPath)
        .where(
            LearningPath.student_id == student.id,
            LearningPath.state == PathState.CURRENT,
        )
        .options(selectinload(LearningPath.items))
        .order_by(LearningPath.created_at.desc())
    )
    targets = list(
        db.scalars(
            select(KnowledgePoint)
            .where(KnowledgePoint.is_active.is_(True))
            .order_by(KnowledgePoint.difficulty.desc(), KnowledgePoint.id)
        )
    )
    return StudentDashboard(
        student_id=student.id,
        student_no=student.student_no,
        display_name=student.user.display_name,
        classroom_name=student.classroom.name,
        algorithm=diagnosis.algorithm,
        average_mastery=round(sum(item.score for item in diagnosis.items) / len(diagnosis.items), 6),
        dimensions=[
            DimensionMastery(dimension=dimension, average=round(sum(scores) / len(scores), 6))
            for dimension, scores in sorted(dimensions.items(), key=lambda item: item[0].value)
        ],
        mastery_items=diagnosis.items,
        weak_points=diagnosis.weak_points,
        suggested_directions=diagnosis.suggested_directions,
        available_targets=[KnowledgePointRead.model_validate(item) for item in targets],
        current_paths=[path_to_read(db, item) for item in paths],
    )


@router.post("/me/behavior/visits", response_model=BehaviorFeedback)
def record_visit(
    payload: VisitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> BehaviorFeedback:
    student = current_student(user)
    point_or_404(db, payload.knowledge_point_id)
    db.add(
        KnowledgeVisit(
            student_id=student.id,
            knowledge_point_id=payload.knowledge_point_id,
            visited_at=datetime.now(UTC),
            duration_seconds=payload.duration_seconds,
        )
    )
    db.commit()
    recompute_rule_mastery(db, [student.id])
    config = db.get(RecommendationConfig, 1)
    if config and config.diagnostic_algorithm == MasteryAlgorithm.BKT:
        recompute_bkt_mastery(db, [student.id])
    return finish_feedback(
        db,
        student_id=student.id,
        point_id=payload.knowledge_point_id,
        message="访问记录已保存",
    )


@router.post("/me/behavior/exercises", response_model=BehaviorFeedback)
def record_exercise(
    payload: ExerciseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> BehaviorFeedback:
    student = current_student(user)
    point_or_404(db, payload.knowledge_point_id)
    db.add(
        ExerciseAttempt(
            student_id=student.id,
            knowledge_point_id=payload.knowledge_point_id,
            attempted_at=datetime.now(UTC),
            is_correct=payload.is_correct,
        )
    )
    db.commit()
    recompute_rule_mastery(db, [student.id])
    recompute_bkt_mastery(db, [student.id])
    return finish_feedback(
        db,
        student_id=student.id,
        point_id=payload.knowledge_point_id,
        message="练习结果已保存",
    )


@router.put("/me/behavior/video-progress", response_model=BehaviorFeedback)
def update_video_progress(
    payload: VideoProgressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> BehaviorFeedback:
    student = current_student(user)
    point_or_404(db, payload.knowledge_point_id)
    progress = db.scalar(
        select(VideoProgress).where(
            VideoProgress.student_id == student.id,
            VideoProgress.knowledge_point_id == payload.knowledge_point_id,
        )
    )
    if progress is None:
        progress = VideoProgress(
            student_id=student.id,
            knowledge_point_id=payload.knowledge_point_id,
            progress_percent=payload.progress_percent,
        )
        db.add(progress)
    else:
        progress.progress_percent = payload.progress_percent
    db.commit()
    config = db.get(RecommendationConfig, 1)
    algorithm = config.diagnostic_algorithm if config else MasteryAlgorithm.BKT
    existing = db.scalar(
        select(MasteryResult).where(
            MasteryResult.student_id == student.id,
            MasteryResult.knowledge_point_id == payload.knowledge_point_id,
            MasteryResult.algorithm == algorithm,
        )
    )
    if existing is None:
        updater = recompute_rule_mastery if algorithm == MasteryAlgorithm.RULE else recompute_bkt_mastery
        updater(db, [student.id])
    return finish_feedback(
        db,
        student_id=student.id,
        point_id=payload.knowledge_point_id,
        message="视频进度已更新",
    )
