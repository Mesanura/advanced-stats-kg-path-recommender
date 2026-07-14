from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.db import get_db
from app.enums import MasteryAlgorithm, Role
from app.models import Classroom, Grade, StudentProfile, TeacherClass, User
from app.schemas.teacher import ScopeClass, TeacherOverview, TeacherScope
from app.services.analytics import build_overview

router = APIRouter(
    prefix="/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_roles(Role.TEACHER, Role.ADMIN))],
)


def assigned_class_ids(db: Session, user: User) -> set[int]:
    if user.role == Role.ADMIN:
        return set(db.scalars(select(Classroom.id)))
    return set(
        db.scalars(select(TeacherClass.classroom_id).where(TeacherClass.teacher_id == user.id))
    )


@router.get("/scope", response_model=TeacherScope)
def scope(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.TEACHER, Role.ADMIN)),
) -> TeacherScope:
    class_ids = assigned_class_ids(db, user)
    classrooms = db.scalars(
        select(Classroom)
        .where(Classroom.id.in_(class_ids))
        .options(selectinload(Classroom.grade))
        .order_by(Classroom.id)
    )
    return TeacherScope(
        classes=[
            ScopeClass(
                id=item.id,
                name=item.name,
                grade_id=item.grade_id,
                grade_name=item.grade.name,
            )
            for item in classrooms
        ]
    )


@router.get("/overview", response_model=TeacherOverview)
def overview(
    class_id: int | None = None,
    grade_id: int | None = None,
    algorithm: MasteryAlgorithm = MasteryAlgorithm.BKT,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.TEACHER, Role.ADMIN)),
) -> TeacherOverview:
    if class_id and grade_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="班级和年级筛选不能同时使用",
        )
    allowed_classes = assigned_class_ids(db, user)
    if class_id:
        if class_id not in allowed_classes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该班级")
        selected_classes = {class_id}
    elif grade_id:
        grade = db.get(Grade, grade_id)
        if grade is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="年级不存在")
        grade_classes = set(
            db.scalars(select(Classroom.id).where(Classroom.grade_id == grade_id))
        )
        if user.role != Role.ADMIN and not grade_classes.intersection(allowed_classes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该年级")
        selected_classes = grade_classes
    else:
        selected_classes = allowed_classes

    student_ids = list(
        db.scalars(
            select(StudentProfile.id).where(StudentProfile.classroom_id.in_(selected_classes))
        )
    )
    attention_classes = selected_classes if user.role == Role.ADMIN else selected_classes.intersection(allowed_classes)
    attention_ids = set(
        db.scalars(
            select(StudentProfile.id).where(StudentProfile.classroom_id.in_(attention_classes))
        )
    )
    return build_overview(
        db,
        student_ids=student_ids,
        attention_student_ids=attention_ids,
        algorithm=algorithm,
    )

