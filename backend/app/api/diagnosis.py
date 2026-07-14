from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, require_roles
from app.db import get_db
from app.enums import MasteryAlgorithm, MasteryStatus, Role
from app.models import KnowledgePoint, MasteryResult, StudentProfile, TeacherClass, User
from app.schemas.diagnosis import MasteryItemRead, RecomputeResponse, StudentDiagnosisRead
from app.services.diagnosis import recompute_rule_mastery

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


def student_or_404(db: Session, student_id: int) -> StudentProfile:
    student = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .options(selectinload(StudentProfile.user), selectinload(StudentProfile.classroom))
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学生不存在")
    return student


def ensure_student_access(db: Session, current_user: User, student: StudentProfile) -> None:
    if current_user.role == Role.ADMIN:
        return
    if current_user.role == Role.STUDENT and student.user_id == current_user.id:
        return
    if current_user.role == Role.TEACHER and db.get(
        TeacherClass, (current_user.id, student.classroom_id)
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该学生")


def build_diagnosis(
    db: Session,
    student: StudentProfile,
    algorithm: MasteryAlgorithm,
) -> StudentDiagnosisRead:
    rows = db.execute(
        select(MasteryResult, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == MasteryResult.knowledge_point_id)
        .where(
            MasteryResult.student_id == student.id,
            MasteryResult.algorithm == algorithm,
            KnowledgePoint.is_active.is_(True),
        )
        .order_by(KnowledgePoint.chapter, KnowledgePoint.id)
    ).all()
    if not rows and algorithm == MasteryAlgorithm.RULE:
        recompute_rule_mastery(db, [student.id])
        return build_diagnosis(db, student, algorithm)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该算法尚未生成诊断结果")

    items = [
        MasteryItemRead(
            knowledge_point_id=point.id,
            name=point.name,
            chapter=point.chapter,
            dimension=point.dimension,
            difficulty=point.difficulty,
            score=result.score,
            status=result.status,
            evidence_count=result.evidence_count,
        )
        for result, point in rows
    ]
    weak_points = [item.name for item in items if item.status == MasteryStatus.WEAK]
    weak_dimensions = Counter(
        item.dimension.value for item in items if item.status in (MasteryStatus.WEAK, MasteryStatus.UNKNOWN)
    )
    suggested_directions = [name for name, _ in weak_dimensions.most_common(2)]
    return StudentDiagnosisRead(
        student_id=student.id,
        student_no=student.student_no,
        display_name=student.user.display_name,
        algorithm=algorithm,
        calculated_at=max(result.calculated_at for result, _ in rows) or datetime.now(UTC),
        items=items,
        weak_points=weak_points,
        suggested_directions=suggested_directions,
    )


@router.get("/me", response_model=StudentDiagnosisRead)
def my_diagnosis(
    algorithm: MasteryAlgorithm = MasteryAlgorithm.RULE,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.STUDENT)),
) -> StudentDiagnosisRead:
    if user.student_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学生档案不存在")
    student = student_or_404(db, user.student_profile.id)
    return build_diagnosis(db, student, algorithm)


@router.get("/students/{student_id}", response_model=StudentDiagnosisRead)
def student_diagnosis(
    student_id: int,
    algorithm: MasteryAlgorithm = MasteryAlgorithm.RULE,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.TEACHER, Role.ADMIN)),
) -> StudentDiagnosisRead:
    student = student_or_404(db, student_id)
    ensure_student_access(db, user, student)
    return build_diagnosis(db, student, algorithm)


@router.post("/recompute", response_model=RecomputeResponse)
def recompute(
    algorithm: MasteryAlgorithm = MasteryAlgorithm.RULE,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.TEACHER, Role.ADMIN)),
) -> RecomputeResponse:
    if algorithm != MasteryAlgorithm.RULE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该算法尚未实现")
    if user.role == Role.ADMIN:
        student_ids = list(db.scalars(select(StudentProfile.id)))
    else:
        classroom_ids = select(TeacherClass.classroom_id).where(TeacherClass.teacher_id == user.id)
        student_ids = list(
            db.scalars(select(StudentProfile.id).where(StudentProfile.classroom_id.in_(classroom_ids)))
        )
    return RecomputeResponse(
        algorithm=algorithm,
        results_updated=recompute_rule_mastery(db, student_ids),
    )

