from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentProfile, User
from app.services.simulation import seed_demo_data


def test_student_dashboard_contains_profile_and_mastery(
    client: TestClient, db_session: Session
) -> None:
    seed_demo_data(db_session, export_dir=None)
    student = db_session.scalar(select(StudentProfile).order_by(StudentProfile.id))
    assert student is not None
    user = db_session.get(User, student.user_id)
    assert user is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Student@123456"},
    )

    response = client.get("/api/v1/students/me/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["student_no"] == student.student_no
    assert len(data["dimensions"]) == 5
    assert len(data["mastery_items"]) == 25
    assert len(data["available_targets"]) == 25

