import networkx as nx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import Role
from app.models import User
from app.security import hash_password


def login(client: TestClient, db: Session, role: Role) -> None:
    user = User(
        username=f"{role.value}_knowledge",
        display_name="知识图谱用户",
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


def test_teacher_imports_default_dag(client: TestClient, db_session: Session) -> None:
    login(client, db_session, Role.TEACHER)

    imported = client.post("/api/v1/knowledge/import-defaults")
    assert imported.status_code == 200
    assert imported.json()["knowledge_points_created"] == 25

    graph_response = client.get("/api/v1/knowledge/graph")
    graph_data = graph_response.json()
    assert len(graph_data["nodes"]) == 25
    graph = nx.DiGraph(
        (item["prerequisite_id"], item["knowledge_point_id"]) for item in graph_data["edges"]
    )
    assert nx.is_directed_acyclic_graph(graph)

    second_import = client.post("/api/v1/knowledge/import-defaults")
    assert second_import.json() == {"knowledge_points_created": 0, "prerequisites_created": 0}


def test_cycle_is_rejected(client: TestClient, db_session: Session) -> None:
    login(client, db_session, Role.TEACHER)
    client.post("/api/v1/knowledge/import-defaults")
    points = client.get("/api/v1/knowledge/points").json()
    ids = {item["code"]: item["id"] for item in points}

    response = client.post(
        "/api/v1/knowledge/prerequisites",
        json={
            "knowledge_point_id": ids["descriptive_statistics"],
            "prerequisite_id": ids["support_vector_machine"],
        },
    )

    assert response.status_code == 422
    assert "循环" in response.json()["detail"]


def test_student_can_read_but_not_edit(client: TestClient, db_session: Session) -> None:
    login(client, db_session, Role.STUDENT)

    assert client.get("/api/v1/knowledge/points").status_code == 200
    response = client.post(
        "/api/v1/knowledge/points",
        json={
            "code": "new_point",
            "name": "新知识点",
            "chapter": "测试章节",
            "dimension": "statistics_foundation",
            "difficulty": 1,
            "resource_url": "https://example.com/resource",
        },
    )
    assert response.status_code == 403


def test_crud_filter_and_confirmed_delete(client: TestClient, db_session: Session) -> None:
    login(client, db_session, Role.ADMIN)
    created = client.post(
        "/api/v1/knowledge/points",
        json={
            "code": "experimental_design",
            "name": "实验设计",
            "chapter": "第六章 实验设计",
            "dimension": "statistics_foundation",
            "difficulty": 3,
            "resource_url": "https://example.com/experimental-design",
        },
    )
    assert created.status_code == 201
    point_id = created.json()["id"]

    filtered = client.get("/api/v1/knowledge/points", params={"difficulty": 3})
    assert [item["code"] for item in filtered.json()] == ["experimental_design"]

    assert client.delete(f"/api/v1/knowledge/points/{point_id}").status_code == 400
    assert client.delete(
        f"/api/v1/knowledge/points/{point_id}", params={"confirm": True}
    ).status_code == 200

