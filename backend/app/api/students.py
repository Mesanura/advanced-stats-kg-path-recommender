from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.api.diagnosis import build_diagnosis, student_or_404
from app.api.recommendations import path_to_read
from app.db import get_db
from app.enums import MasteryAlgorithm, PathState, Role
from app.models import KnowledgePoint, LearningPath, RecommendationConfig, User
from app.schemas.knowledge import KnowledgePointRead
from app.schemas.student import DimensionMastery, StudentDashboard

router = APIRouter(prefix="/students", tags=["students"])


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
