from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import AbilityDimension, MasteryAlgorithm, MasteryStatus, Role
from app.models import (
    Classroom,
    ExerciseAttempt,
    Grade,
    KnowledgePoint,
    KnowledgeVisit,
    MasteryResult,
    StudentProfile,
    TeacherClass,
    User,
)
from app.security import hash_password
from app.services.diagnosis import calculate_rule_score, recompute_rule_mastery
from app.services.simulation import seed_demo_data


def test_rule_formula_and_status(db_session: Session) -> None:
    grade = Grade(name="2026级")
    classroom = Classroom(name="01班", grade=grade)
    user = User(username="s1", display_name="学生", role=Role.STUDENT, password_hash="hash")
    student = StudentProfile(user=user, student_no="1", classroom=classroom)
    point = KnowledgePoint(
        code="test_point",
        name="测试知识点",
        chapter="测试",
        dimension=AbilityDimension.STATISTICS_FOUNDATION,
        difficulty=1,
        resource_url="https://example.com",
    )
    db_session.add_all([student, point])
    db_session.flush()
    db_session.add_all(
        [
            ExerciseAttempt(student_id=student.id, knowledge_point_id=point.id, attempted_at=datetime.now(UTC), is_correct=True),
            ExerciseAttempt(student_id=student.id, knowledge_point_id=point.id, attempted_at=datetime.now(UTC), is_correct=False),
            KnowledgeVisit(student_id=student.id, knowledge_point_id=point.id, visited_at=datetime.now(UTC), duration_seconds=600),
            KnowledgeVisit(student_id=student.id, knowledge_point_id=point.id, visited_at=datetime.now(UTC), duration_seconds=600),
            KnowledgeVisit(student_id=student.id, knowledge_point_id=point.id, visited_at=datetime.now(UTC), duration_seconds=600),
        ]
    )
    db_session.commit()

    assert calculate_rule_score(correct=1, attempts=2, visit_count=3, duration_seconds=1800) == (0.7, 5)
    recompute_rule_mastery(db_session, [student.id])
    result = db_session.scalar(select(MasteryResult))
    assert result is not None
    assert result.status == MasteryStatus.MASTERED


def test_rule_recompute_creates_all_results(db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)

    assert recompute_rule_mastery(db_session) == 1250
    count = db_session.scalar(
        select(func.count()).select_from(MasteryResult).where(
            MasteryResult.algorithm == MasteryAlgorithm.RULE
        )
    )
    assert count == 1250


def test_student_reads_own_diagnosis(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    recompute_rule_mastery(db_session)
    student = db_session.scalar(select(StudentProfile).order_by(StudentProfile.id))
    assert student is not None
    login = client.post(
        "/api/v1/auth/login",
        json={"username": student.user.username, "password": "Student@123456"},
    )
    assert login.status_code == 200

    response = client.get("/api/v1/diagnosis/me")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 25
    assert response.json()["student_id"] == student.id


def test_teacher_cannot_read_unassigned_class(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    teacher = db_session.scalar(select(User).where(User.username == "teacher01"))
    target = db_session.scalar(
        select(StudentProfile).where(StudentProfile.classroom_id != teacher.teacher_assignments[0].classroom_id)
    )
    assert teacher is not None and target is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": "Teacher@123456"},
    )

    assert client.get(f"/api/v1/diagnosis/students/{target.id}").status_code == 403

