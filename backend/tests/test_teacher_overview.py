from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Classroom, User
from app.services.simulation import seed_demo_data


def login_teacher(client: TestClient, db: Session) -> User:
    teacher = db.scalar(select(User).where(User.username == "teacher01"))
    assert teacher is not None
    response = client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": "Teacher@123456"},
    )
    assert response.status_code == 200
    return teacher


def test_teacher_class_and_grade_overview(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    login_teacher(client, db_session)
    scope = client.get("/api/v1/teacher/scope").json()
    assert len(scope["classes"]) == 1
    classroom = scope["classes"][0]

    class_overview = client.get(
        "/api/v1/teacher/overview",
        params={"class_id": classroom["id"], "algorithm": "rule"},
    )
    assert class_overview.status_code == 200
    assert class_overview.json()["student_count"] == 25
    assert len(class_overview.json()["knowledge_points"]) == 25
    assert len(class_overview.json()["weak_top5"]) == 5

    grade_overview = client.get(
        "/api/v1/teacher/overview",
        params={"grade_id": classroom["grade_id"], "algorithm": "bkt"},
    )
    assert grade_overview.status_code == 200
    assert grade_overview.json()["student_count"] == 50
    assert all(
        item["classroom_name"] == classroom["name"]
        for item in grade_overview.json()["attention_students"]
    )


def test_teacher_cannot_open_other_class(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    teacher = login_teacher(client, db_session)
    assigned = teacher.teacher_assignments[0].classroom_id
    other = db_session.scalar(select(Classroom).where(Classroom.id != assigned))
    assert other is not None

    response = client.get("/api/v1/teacher/overview", params={"class_id": other.id})
    assert response.status_code == 403

