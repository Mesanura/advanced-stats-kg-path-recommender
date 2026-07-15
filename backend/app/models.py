from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import (
    AbilityDimension,
    MasteryAlgorithm,
    MasteryStatus,
    PathNodeStatus,
    PathState,
    Role,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Grade(Base, TimestampMixin):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    classrooms: Mapped[list["Classroom"]] = relationship(
        back_populates="grade", cascade="all, delete-orphan"
    )


class Classroom(Base, TimestampMixin):
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("grade_id", "name", name="uq_classroom_grade_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    grade: Mapped[Grade] = relationship(back_populates="classrooms")
    students: Mapped[list["StudentProfile"]] = relationship(back_populates="classroom")
    teacher_assignments: Mapped[list["TeacherClass"]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False, length=20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", single_parent=True
    )
    teacher_assignments: Mapped[list["TeacherClass"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    student_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True
    )
    user: Mapped[User] = relationship(back_populates="student_profile")
    classroom: Mapped[Classroom] = relationship(back_populates="students")
    visits: Mapped[list["KnowledgeVisit"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    exercise_attempts: Mapped[list["ExerciseAttempt"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    video_progress: Mapped[list["VideoProgress"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    mastery_results: Mapped[list["MasteryResult"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    learning_paths: Mapped[list["LearningPath"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True
    )
    teacher: Mapped[User] = relationship(back_populates="teacher_assignments")
    classroom: Mapped[Classroom] = relationship(back_populates="teacher_assignments")


class KnowledgePoint(Base, TimestampMixin):
    __tablename__ = "knowledge_points"
    __table_args__ = (CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_knowledge_difficulty"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    chapter: Mapped[str] = mapped_column(String(100), index=True)
    dimension: Mapped[AbilityDimension] = mapped_column(
        SqlEnum(AbilityDimension, native_enum=False, length=40), index=True
    )
    difficulty: Mapped[int] = mapped_column(Integer)
    resource_url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class Prerequisite(Base, TimestampMixin):
    __tablename__ = "prerequisites"
    __table_args__ = (
        CheckConstraint("knowledge_point_id <> prerequisite_id", name="ck_prerequisite_not_self"),
    )

    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True
    )
    prerequisite_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True
    )


class KnowledgeVisit(Base):
    __tablename__ = "knowledge_visits"
    __table_args__ = (CheckConstraint("duration_seconds >= 0", name="ck_visit_duration"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    student: Mapped[StudentProfile] = relationship(back_populates="visits")


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    student: Mapped[StudentProfile] = relationship(back_populates="exercise_attempts")


class VideoProgress(Base):
    __tablename__ = "video_progress"
    __table_args__ = (
        UniqueConstraint("student_id", "knowledge_point_id", name="uq_video_student_knowledge"),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_video_progress"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    progress_percent: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    student: Mapped[StudentProfile] = relationship(back_populates="video_progress")


class LatentMastery(Base):
    __tablename__ = "latent_mastery"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 1", name="ck_latent_score"),)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float)


class MasteryResult(Base):
    __tablename__ = "mastery_results"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "knowledge_point_id", "algorithm", name="uq_mastery_student_knowledge_algorithm"
        ),
        CheckConstraint("score BETWEEN 0 AND 1", name="ck_mastery_score"),
        Index("ix_mastery_algorithm_status", "algorithm", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    algorithm: Mapped[MasteryAlgorithm] = mapped_column(
        SqlEnum(MasteryAlgorithm, native_enum=False, length=20)
    )
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[MasteryStatus] = mapped_column(
        SqlEnum(MasteryStatus, native_enum=False, length=20), index=True
    )
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    student: Mapped[StudentProfile] = relationship(back_populates="mastery_results")


class RecommendationConfig(Base):
    __tablename__ = "recommendation_configs"
    __table_args__ = (
        CheckConstraint("min_path_length >= 1", name="ck_config_min_length"),
        CheckConstraint("max_path_length >= min_path_length", name="ck_config_length_order"),
        CheckConstraint("mastery_threshold BETWEEN 0 AND 1", name="ck_config_mastery_threshold"),
        CheckConstraint("weak_threshold BETWEEN 0 AND 1", name="ck_config_weak_threshold"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    diagnostic_algorithm: Mapped[MasteryAlgorithm] = mapped_column(
        SqlEnum(MasteryAlgorithm, native_enum=False, length=20), default=MasteryAlgorithm.BKT
    )
    min_path_length: Mapped[int] = mapped_column(Integer, default=5)
    max_path_length: Mapped[int] = mapped_column(Integer, default=8)
    mastery_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    weak_threshold: Mapped[float] = mapped_column(Float, default=0.5)
    weak_priority_weight: Mapped[float] = mapped_column(Float, default=0.45)
    mastered_alignment_weight: Mapped[float] = mapped_column(Float, default=0.25)
    length_penalty_weight: Mapped[float] = mapped_column(Float, default=0.15)
    difficulty_jump_weight: Mapped[float] = mapped_column(Float, default=0.15)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningPath(Base):
    __tablename__ = "learning_paths"
    __table_args__ = (Index("ix_path_student_state", "student_id", "state"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    target_knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    algorithm: Mapped[MasteryAlgorithm] = mapped_column(
        SqlEnum(MasteryAlgorithm, native_enum=False, length=20)
    )
    state: Mapped[PathState] = mapped_column(
        SqlEnum(PathState, native_enum=False, length=20), default=PathState.CURRENT, index=True
    )
    score: Mapped[float] = mapped_column(Float)
    length_exception: Mapped[str | None] = mapped_column(String(100))
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    student: Mapped[StudentProfile] = relationship(back_populates="learning_paths")
    items: Mapped[list["LearningPathItem"]] = relationship(
        back_populates="path", cascade="all, delete-orphan", order_by="LearningPathItem.sequence"
    )


class LearningPathItem(Base):
    __tablename__ = "learning_path_items"
    __table_args__ = (
        UniqueConstraint("path_id", "knowledge_point_id", name="uq_path_knowledge_point"),
        CheckConstraint("mastery_score BETWEEN 0 AND 1", name="ck_path_item_mastery"),
    )

    path_id: Mapped[int] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage: Mapped[int] = mapped_column(Integer, default=1)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[PathNodeStatus] = mapped_column(
        SqlEnum(PathNodeStatus, native_enum=False, length=20)
    )
    mastery_score: Mapped[float] = mapped_column(Float)
    path: Mapped[LearningPath] = relationship(back_populates="items")
