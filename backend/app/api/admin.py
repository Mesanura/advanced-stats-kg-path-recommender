from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_roles
from app.db import get_db
from app.enums import Role
from app.models import Classroom, Grade, StudentProfile, TeacherClass, User
from app.schemas.admin import (
    ClassroomCreate,
    ClassroomRead,
    GradeCreate,
    GradeRead,
    PaginatedUsers,
    PasswordReset,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.schemas.auth import MessageResponse
from app.security import hash_password

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles(Role.ADMIN))],
)


def user_to_read(user: User) -> UserRead:
    profile = user.student_profile
    teacher_classrooms = sorted(
        (assignment.classroom for assignment in user.teacher_assignments),
        key=lambda classroom: classroom.id,
    )
    return UserRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        student_no=profile.student_no if profile else None,
        classroom_id=profile.classroom_id if profile else None,
        classroom_name=profile.classroom.name if profile else None,
        classroom_ids=[item.id for item in teacher_classrooms],
        classrooms=[
            ClassroomRead(
                id=item.id,
                grade_id=item.grade_id,
                grade_name=item.grade.name,
                name=item.name,
            )
            for item in teacher_classrooms
        ],
    )


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.student_profile).selectinload(StudentProfile.classroom),
            selectinload(User.teacher_assignments)
            .selectinload(TeacherClass.classroom)
            .selectinload(Classroom.grade),
        )
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.get("/grades", response_model=list[GradeRead])
def list_grades(db: Session = Depends(get_db)) -> list[GradeRead]:
    return [GradeRead(id=item.id, name=item.name) for item in db.scalars(select(Grade).order_by(Grade.id))]


@router.post("/grades", response_model=GradeRead, status_code=status.HTTP_201_CREATED)
def create_grade(payload: GradeCreate, db: Session = Depends(get_db)) -> GradeRead:
    if db.scalar(select(Grade).where(Grade.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="年级名称已存在")
    grade = Grade(name=payload.name)
    db.add(grade)
    db.commit()
    return GradeRead(id=grade.id, name=grade.name)


@router.get("/classes", response_model=list[ClassroomRead])
def list_classrooms(db: Session = Depends(get_db)) -> list[ClassroomRead]:
    classrooms = db.scalars(select(Classroom).options(selectinload(Classroom.grade)).order_by(Classroom.id))
    return [
        ClassroomRead(id=item.id, grade_id=item.grade_id, grade_name=item.grade.name, name=item.name)
        for item in classrooms
    ]


@router.post("/classes", response_model=ClassroomRead, status_code=status.HTTP_201_CREATED)
def create_classroom(payload: ClassroomCreate, db: Session = Depends(get_db)) -> ClassroomRead:
    grade = db.get(Grade, payload.grade_id)
    if grade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="年级不存在")
    exists = db.scalar(
        select(Classroom).where(Classroom.grade_id == payload.grade_id, Classroom.name == payload.name)
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="班级名称已存在")
    classroom = Classroom(grade=grade, name=payload.name)
    db.add(classroom)
    db.commit()
    return ClassroomRead(
        id=classroom.id,
        grade_id=classroom.grade_id,
        grade_name=grade.name,
        name=classroom.name,
    )


@router.get("/users", response_model=PaginatedUsers)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    query: str | None = Query(default=None, max_length=80),
    role: Role | None = None,
    db: Session = Depends(get_db),
) -> PaginatedUsers:
    statement = select(User)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))
    if role:
        statement = statement.where(User.role == role)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    users = db.scalars(
        statement.options(
            selectinload(User.student_profile).selectinload(StudentProfile.classroom),
            selectinload(User.teacher_assignments)
            .selectinload(TeacherClass.classroom)
            .selectinload(Classroom.grade),
        )
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return PaginatedUsers(
        items=[user_to_read(item) for item in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    return user_to_read(get_user_or_404(db, user_id))


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    if payload.student_no and db.scalar(
        select(StudentProfile).where(StudentProfile.student_no == payload.student_no)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="学号已存在")

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    if payload.role == Role.STUDENT:
        classroom = db.get(Classroom, payload.classroom_id)
        if classroom is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="班级不存在")
        user.student_profile = StudentProfile(
            student_no=payload.student_no or "",
            classroom=classroom,
        )
    elif payload.role == Role.TEACHER:
        classrooms = list(db.scalars(select(Classroom).where(Classroom.id.in_(payload.classroom_ids))))
        if len(classrooms) != len(set(payload.classroom_ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="包含不存在的班级")
        user.teacher_assignments = [TeacherClass(classroom_id=item.id) for item in classrooms]

    db.commit()
    return user_to_read(get_user_or_404(db, user.id))


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> UserRead:
    user = get_user_or_404(db, user_id)
    if payload.username is not None:
        duplicate = db.scalar(
            select(User).where(User.username == payload.username, User.id != user.id)
        )
        if duplicate is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
        user.username = payload.username
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.is_active is not None:
        if user.id == current_user.id and not payload.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能停用当前管理员")
        user.is_active = payload.is_active
    if payload.student_no is not None:
        if user.role != Role.STUDENT or user.student_profile is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅学生可修改学号")
        duplicate_profile = db.scalar(
            select(StudentProfile).where(
                StudentProfile.student_no == payload.student_no,
                StudentProfile.user_id != user.id,
            )
        )
        if duplicate_profile is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="学号已存在")
        user.student_profile.student_no = payload.student_no
    if payload.classroom_id is not None:
        if user.role != Role.STUDENT or user.student_profile is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅学生可调整班级")
        classroom = db.get(Classroom, payload.classroom_id)
        if classroom is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="班级不存在")
        user.student_profile.classroom = classroom
    if payload.classroom_ids is not None:
        if user.role != Role.TEACHER:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅教师可分配班级")
        classrooms = list(db.scalars(select(Classroom).where(Classroom.id.in_(payload.classroom_ids))))
        if len(classrooms) != len(set(payload.classroom_ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="包含不存在的班级")
        user.teacher_assignments = [TeacherClass(classroom_id=item.id) for item in classrooms]
    db.commit()
    return user_to_read(get_user_or_404(db, user.id))


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = get_user_or_404(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能删除当前管理员")
    db.delete(user)
    db.commit()
    return MessageResponse(message="用户已删除")


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
def reset_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db)) -> MessageResponse:
    user = get_user_or_404(db, user_id)
    user.password_hash = hash_password(payload.password)
    db.commit()
    return MessageResponse(message="密码已重置")
