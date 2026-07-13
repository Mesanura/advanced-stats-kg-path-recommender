from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import Role
from app.models import User
from app.security import hash_password


def login_as(client: TestClient, db: Session, role: Role) -> User:
    user = User(
        username=f"{role.value}01",
        display_name=f"{role.value}用户",
        role=role,
        password_hash=hash_password("Password@123"),
    )
    db.add(user)
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Password@123"},
    )
    assert response.status_code == 200
    return user


def test_student_cannot_access_admin_api(client: TestClient, db_session: Session) -> None:
    login_as(client, db_session, Role.STUDENT)

    assert client.get("/api/v1/admin/users").status_code == 403


def test_admin_manages_grades_classes_and_users(client: TestClient, db_session: Session) -> None:
    login_as(client, db_session, Role.ADMIN)

    grade = client.post("/api/v1/admin/grades", json={"name": "2026级"})
    assert grade.status_code == 201
    classroom = client.post(
        "/api/v1/admin/classes",
        json={"grade_id": grade.json()["id"], "name": "高级统计01班"},
    )
    assert classroom.status_code == 201

    student = client.post(
        "/api/v1/admin/users",
        json={
            "username": "20260001",
            "display_name": "学生01",
            "password": "Student@123456",
            "role": "student",
            "student_no": "20260001",
            "classroom_id": classroom.json()["id"],
        },
    )
    assert student.status_code == 201
    assert student.json()["classroom_name"] == "高级统计01班"

    users = client.get("/api/v1/admin/users", params={"query": "学生"})
    assert users.status_code == 200
    assert users.json()["total"] == 1

    changed = client.patch(
        f"/api/v1/admin/users/{student.json()['id']}",
        json={"is_active": False},
    )
    assert changed.json()["is_active"] is False


def test_admin_assigns_teacher_and_resets_password(client: TestClient, db_session: Session) -> None:
    login_as(client, db_session, Role.ADMIN)
    grade = client.post("/api/v1/admin/grades", json={"name": "2026级"}).json()
    classroom = client.post(
        "/api/v1/admin/classes", json={"grade_id": grade["id"], "name": "高级统计01班"}
    ).json()
    teacher = client.post(
        "/api/v1/admin/users",
        json={
            "username": "teacher01",
            "display_name": "教师01",
            "password": "Teacher@123456",
            "role": "teacher",
            "classroom_ids": [classroom["id"]],
        },
    )
    assert teacher.status_code == 201
    assert teacher.json()["classroom_ids"] == [classroom["id"]]

    reset = client.post(
        f"/api/v1/admin/users/{teacher.json()['id']}/reset-password",
        json={"password": "NewPassword@123"},
    )
    assert reset.status_code == 200

