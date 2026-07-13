from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.enums import Role
from app.models import Classroom, Grade, StudentProfile, User


def test_metadata_contains_all_domain_tables() -> None:
    expected = {
        "grades",
        "classrooms",
        "users",
        "student_profiles",
        "teacher_classes",
        "knowledge_points",
        "prerequisites",
        "knowledge_visits",
        "exercise_attempts",
        "video_progress",
        "latent_mastery",
        "mastery_results",
        "recommendation_configs",
        "learning_paths",
        "learning_path_items",
    }

    assert expected == set(Base.metadata.tables)


def test_user_student_class_relationships() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        grade = Grade(name="2026级")
        classroom = Classroom(name="高级统计01班", grade=grade)
        user = User(
            username="student01",
            password_hash="hash",
            display_name="学生01",
            role=Role.STUDENT,
        )
        profile = StudentProfile(user=user, student_no="20260001", classroom=classroom)
        session.add(profile)
        session.commit()

        assert profile.user.student_profile is profile
        assert profile.classroom.grade.name == "2026级"

