from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import Role
from app.models import User
from app.security import hash_password


def add_user(db: Session, *, active: bool = True, role: Role = Role.STUDENT) -> User:
    user = User(
        username="student01",
        display_name="学生01",
        password_hash=hash_password("Student@123456"),
        role=role,
        is_active=active,
    )
    db.add(user)
    db.commit()
    return user


def test_login_me_and_logout(client: TestClient, db_session: Session) -> None:
    add_user(db_session)
    assert client.get("/api/v1/auth/session").json() == {"user": None}

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "student01", "password": "Student@123456"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "student"
    assert login.cookies.get("access_token")
    assert client.get("/api/v1/auth/session").json()["user"]["display_name"] == "学生01"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "学生01"

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/session").json() == {"user": None}
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rejects_wrong_password(client: TestClient, db_session: Session) -> None:
    add_user(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student01", "password": "WrongPassword"},
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(client: TestClient, db_session: Session) -> None:
    add_user(db_session, active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student01", "password": "Student@123456"},
    )

    assert response.status_code == 401
