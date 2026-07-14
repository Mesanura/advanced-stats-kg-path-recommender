from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.simulation import seed_demo_data


def login_teacher(client: TestClient, db: Session) -> None:
    teacher = db.scalar(select(User).where(User.username == "teacher01"))
    assert teacher is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": "Teacher@123456"},
    )


def test_teacher_searches_assigned_students(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    login_teacher(client, db_session)

    response = client.get(
        "/api/v1/teacher/students",
        params={"query": "学生01", "algorithm": "rule"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    student = response.json()["items"][0]
    assert student["student_no"] == "20260001"

    diagnosis = client.get(
        f"/api/v1/teacher/students/{student['student_id']}/diagnosis",
        params={"algorithm": "bkt"},
    )
    assert diagnosis.status_code == 200
    assert len(diagnosis.json()["items"]) == 25


def test_teacher_search_excludes_other_class(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    login_teacher(client, db_session)

    response = client.get("/api/v1/teacher/students", params={"query": "20260026"})
    assert response.status_code == 200
    assert response.json()["total"] == 0

