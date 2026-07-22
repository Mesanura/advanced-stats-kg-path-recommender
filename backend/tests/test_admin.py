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
    admin = login_as(client, db_session, Role.ADMIN)

    grade = client.post("/api/v1/admin/grades", json={"name": "2026级"})
    assert grade.status_code == 201
    classroom = client.post(
        "/api/v1/admin/classes",
        json={"grade_id": grade.json()["id"], "name": "高级统计01班"},
    )
    assert classroom.status_code == 201
    second_classroom = client.post(
        "/api/v1/admin/classes",
        json={"grade_id": grade.json()["id"], "name": "高级统计02班"},
    ).json()

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
        json={
            "username": "20260002",
            "display_name": "学生02",
            "student_no": "20260002",
            "classroom_id": second_classroom["id"],
            "is_active": False,
        },
    )
    assert changed.status_code == 200
    assert changed.json()["username"] == "20260002"
    assert changed.json()["student_no"] == "20260002"
    assert changed.json()["classroom_name"] == "高级统计02班"
    assert changed.json()["is_active"] is False

    detail = client.get(f"/api/v1/admin/users/{student.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["display_name"] == "学生02"

    assert client.patch(f"/api/v1/admin/users/{admin.id}", json={"is_active": False}).status_code == 409
    assert client.delete(f"/api/v1/admin/users/{admin.id}").status_code == 409

    deleted = client.delete(f"/api/v1/admin/users/{student.json()['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "用户已删除"
    assert client.get(f"/api/v1/admin/users/{student.json()['id']}").status_code == 404


def test_admin_assigns_teacher_and_resets_password(client: TestClient, db_session: Session) -> None:
    login_as(client, db_session, Role.ADMIN)
    grade = client.post("/api/v1/admin/grades", json={"name": "2026级"}).json()
    classroom = client.post(
        "/api/v1/admin/classes", json={"grade_id": grade["id"], "name": "高级统计01班"}
    ).json()
    second_classroom = client.post(
        "/api/v1/admin/classes", json={"grade_id": grade["id"], "name": "高级统计02班"}
    ).json()
    teacher = client.post(
        "/api/v1/admin/users",
        json={
            "username": "teacher01",
            "display_name": "教师01",
            "password": "Teacher@123456",
            "role": "teacher",
            "classroom_ids": [classroom["id"], second_classroom["id"]],
        },
    )
    assert teacher.status_code == 201
    assert teacher.json()["classroom_ids"] == [classroom["id"], second_classroom["id"]]
    assert [item["name"] for item in teacher.json()["classrooms"]] == [
        "高级统计01班",
        "高级统计02班",
    ]

    reassigned = client.patch(
        f"/api/v1/admin/users/{teacher.json()['id']}",
        json={"classroom_ids": [second_classroom["id"]]},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["classroom_ids"] == [second_classroom["id"]]
    assert reassigned.json()["classrooms"][0]["grade_name"] == "2026级"

    reset = client.post(
        f"/api/v1/admin/users/{teacher.json()['id']}/reset-password",
        json={"password": "NewPassword@123"},
    )
    assert reset.status_code == 200


def test_admin_rejects_duplicate_user_identity(client: TestClient, db_session: Session) -> None:
    login_as(client, db_session, Role.ADMIN)
    grade = client.post("/api/v1/admin/grades", json={"name": "2026级"}).json()
    classroom = client.post(
        "/api/v1/admin/classes", json={"grade_id": grade["id"], "name": "高级统计01班"}
    ).json()

    users = []
    for index in (1, 2):
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": f"2026000{index}",
                "display_name": f"学生0{index}",
                "password": "Student@123456",
                "role": "student",
                "student_no": f"2026000{index}",
                "classroom_id": classroom["id"],
            },
        )
        assert response.status_code == 201
        users.append(response.json())

    duplicate_username = client.patch(
        f"/api/v1/admin/users/{users[1]['id']}", json={"username": users[0]["username"]}
    )
    assert duplicate_username.status_code == 409
    assert duplicate_username.json()["detail"] == "用户名已存在"

    duplicate_student_no = client.patch(
        f"/api/v1/admin/users/{users[1]['id']}", json={"student_no": users[0]["student_no"]}
    )
    assert duplicate_student_no.status_code == 409
    assert duplicate_student_no.json()["detail"] == "学号已存在"
