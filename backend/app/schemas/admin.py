from pydantic import BaseModel, Field, model_validator

from app.enums import Role


class GradeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)


class GradeRead(BaseModel):
    id: int
    name: str


class ClassroomCreate(BaseModel):
    grade_id: int
    name: str = Field(min_length=2, max_length=50)


class ClassroomRead(BaseModel):
    id: int
    grade_id: int
    grade_name: str
    name: str


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]+$", min_length=3, max_length=80)
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: Role
    student_no: str | None = Field(default=None, max_length=30)
    classroom_id: int | None = None
    classroom_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_role_fields(self) -> "UserCreate":
        if self.role == Role.STUDENT and (not self.student_no or not self.classroom_id):
            raise ValueError("学生账号必须提供学号和班级")
        if self.role != Role.STUDENT and (self.student_no or self.classroom_id):
            raise ValueError("仅学生账号可以设置学号和班级")
        if self.role != Role.TEACHER and self.classroom_ids:
            raise ValueError("仅教师账号可以分配负责班级")
        return self


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_.-]+$", min_length=3, max_length=80
    )
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    student_no: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None
    classroom_id: int | None = None
    classroom_ids: list[int] | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    student_no: str | None = None
    classroom_id: int | None = None
    classroom_name: str | None = None
    classroom_ids: list[int] = Field(default_factory=list)
    classrooms: list[ClassroomRead] = Field(default_factory=list)


class PaginatedUsers(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int
