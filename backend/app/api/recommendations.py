from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.api.diagnosis import ensure_student_access, student_or_404
from app.db import get_db
from app.enums import PathState, Role
from app.models import KnowledgePoint, LearningPath, Prerequisite, StudentProfile, User
from app.schemas.recommendation import LearningPathRead, PathNodeRead, RecommendationRequest
from app.services.recommendation import recommend_path

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def path_to_read(db: Session, path: LearningPath) -> LearningPathRead:
    point_ids = [item.knowledge_point_id for item in path.items]
    points = {
        item.id: item
        for item in db.scalars(select(KnowledgePoint).where(KnowledgePoint.id.in_(point_ids)))
    }
    prerequisite_names: dict[int, list[str]] = {point_id: [] for point_id in point_ids}
    edges = db.execute(
        select(Prerequisite, KnowledgePoint.name)
        .join(KnowledgePoint, KnowledgePoint.id == Prerequisite.prerequisite_id)
        .where(Prerequisite.knowledge_point_id.in_(point_ids))
    )
    for edge, name in edges:
        prerequisite_names[edge.knowledge_point_id].append(name)
    target = points[path.target_knowledge_point_id]
    return LearningPathRead(
        id=path.id,
        student_id=path.student_id,
        target_knowledge_point_id=path.target_knowledge_point_id,
        target_name=target.name,
        algorithm=path.algorithm,
        state=path.state,
        score=path.score,
        stage_count=max((item.stage for item in path.items), default=1),
        length_exception=path.length_exception,
        created_at=path.created_at,
        nodes=[
            PathNodeRead(
                sequence=item.sequence,
                stage=item.stage,
                knowledge_point_id=item.knowledge_point_id,
                name=points[item.knowledge_point_id].name,
                difficulty=points[item.knowledge_point_id].difficulty,
                resource_url=points[item.knowledge_point_id].resource_url,
                prerequisites=prerequisite_names[item.knowledge_point_id],
                status=item.status,
                mastery_score=item.mastery_score,
            )
            for item in path.items
        ],
    )


def create_for_student(
    db: Session, student: StudentProfile, payload: RecommendationRequest
) -> LearningPathRead:
    try:
        path = recommend_path(
            db,
            student_id=student.id,
            target_id=payload.target_knowledge_point_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    path = db.scalar(
        select(LearningPath)
        .where(LearningPath.id == path.id)
        .options(selectinload(LearningPath.items))
    )
    assert path is not None
    return path_to_read(db, path)


@router.post("/me", response_model=LearningPathRead)
def recommend_for_me(
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> LearningPathRead:
    if user.student_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学生档案不存在")
    return create_for_student(db, student_or_404(db, user.student_profile.id), payload)


@router.get("/me", response_model=list[LearningPathRead])
def my_paths(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> list[LearningPathRead]:
    if user.student_profile is None:
        return []
    paths = db.scalars(
        select(LearningPath)
        .where(
            LearningPath.student_id == user.student_profile.id,
            LearningPath.state == PathState.CURRENT,
        )
        .options(selectinload(LearningPath.items))
        .order_by(LearningPath.created_at.desc())
    )
    return [path_to_read(db, item) for item in paths]


@router.post("/students/{student_id}", response_model=LearningPathRead)
def recommend_for_student(
    student_id: int,
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.TEACHER, Role.ADMIN)),
) -> LearningPathRead:
    student = student_or_404(db, student_id)
    ensure_student_access(db, user, student)
    return create_for_student(db, student, payload)
