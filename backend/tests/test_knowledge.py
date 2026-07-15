import networkx as nx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathState, Role
from app.models import Classroom, Grade, KnowledgePoint, LearningPath, Prerequisite, StudentProfile, User
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

    filtered = client.get(
        "/api/v1/knowledge/points",
        params={"chapter": "第六章 实验设计", "difficulty": 3},
    )
    assert [item["code"] for item in filtered.json()] == ["experimental_design"]

    patched = client.patch(
        f"/api/v1/knowledge/points/{point_id}",
        json={"name": "实验设计基础"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "实验设计基础"

    duplicate = client.post(
        "/api/v1/knowledge/points",
        json={
            "code": "experimental_design_duplicate",
            "name": "重复实验设计",
            "chapter": "第六章 实验设计",
            "dimension": "statistics_foundation",
            "difficulty": 2,
            "resource_url": "https://example.com/experimental-design-duplicate",
        },
    )
    assert duplicate.status_code == 201
    conflict = client.patch(
        f"/api/v1/knowledge/points/{point_id}",
        json={"name": "重复实验设计"},
    )
    assert conflict.status_code == 409

    assert client.delete(f"/api/v1/knowledge/points/{point_id}").status_code == 400
    assert client.delete(
        f"/api/v1/knowledge/points/{point_id}", params={"confirm": True}
    ).status_code == 200


def test_prerequisite_update_delete_cycle_and_path_invalidation(
    client: TestClient, db_session: Session
) -> None:
    login(client, db_session, Role.TEACHER)
    client.post("/api/v1/knowledge/import-defaults")
    points = {item.code: item for item in db_session.scalars(select(KnowledgePoint))}
    grade = Grade(name="关系测试年级")
    classroom = Classroom(name="关系测试班", grade=grade)
    student_user = User(
        username="relation_student",
        display_name="关系测试学生",
        role=Role.STUDENT,
        password_hash="hash",
    )
    student = StudentProfile(user=student_user, student_no="RELATION001", classroom=classroom)
    db_session.add(student)
    db_session.flush()
    path = LearningPath(
        student_id=student.id,
        target_knowledge_point_id=points["simple_linear_regression"].id,
        algorithm=MasteryAlgorithm.BKT,
        state=PathState.CURRENT,
        score=0.5,
        config_snapshot={},
    )
    db_session.add(path)
    db_session.commit()

    old_target = points["simple_linear_regression"].id
    old_prerequisite = points["descriptive_statistics"].id
    new_prerequisite = points["linear_algebra"].id

    self_relation = client.put(
        f"/api/v1/knowledge/prerequisites/{old_target}/{old_prerequisite}",
        json={"knowledge_point_id": old_target, "prerequisite_id": old_target},
    )
    assert self_relation.status_code == 422
    assert db_session.get(Prerequisite, (old_target, old_prerequisite)) is not None

    duplicate = client.put(
        f"/api/v1/knowledge/prerequisites/{old_target}/{old_prerequisite}",
        json={
            "knowledge_point_id": points["multiple_linear_regression"].id,
            "prerequisite_id": new_prerequisite,
        },
    )
    assert duplicate.status_code == 409
    assert db_session.get(Prerequisite, (old_target, old_prerequisite)) is not None

    updated = client.put(
        f"/api/v1/knowledge/prerequisites/{old_target}/{old_prerequisite}",
        json={"knowledge_point_id": old_target, "prerequisite_id": new_prerequisite},
    )
    assert updated.status_code == 200
    assert db_session.get(Prerequisite, (old_target, old_prerequisite)) is None
    assert db_session.get(Prerequisite, (old_target, new_prerequisite)) is not None
    db_session.refresh(path)
    assert path.state == PathState.STALE

    cycle = client.put(
        f"/api/v1/knowledge/prerequisites/{old_target}/{new_prerequisite}",
        json={
            "knowledge_point_id": points["descriptive_statistics"].id,
            "prerequisite_id": points["support_vector_machine"].id,
        },
    )
    assert cycle.status_code == 422
    assert db_session.get(Prerequisite, (old_target, new_prerequisite)) is not None

    removed = client.delete(
        f"/api/v1/knowledge/prerequisites/{old_target}/{new_prerequisite}"
    )
    assert removed.status_code == 200
    assert db_session.get(Prerequisite, (old_target, new_prerequisite)) is None


@pytest.mark.parametrize("failure_method", ["flush", "commit"])
def test_prerequisite_update_rolls_back_on_write_failure(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    failure_method: str,
) -> None:
    login(client, db_session, Role.TEACHER)
    client.post("/api/v1/knowledge/import-defaults")
    points = {item.code: item for item in db_session.scalars(select(KnowledgePoint))}
    grade = Grade(name=f"回滚测试年级-{failure_method}")
    classroom = Classroom(name=f"回滚测试班-{failure_method}", grade=grade)
    student_user = User(
        username=f"rollback_student_{failure_method}",
        display_name="回滚测试学生",
        role=Role.STUDENT,
        password_hash="hash",
    )
    student = StudentProfile(
        user=student_user,
        student_no=f"ROLLBACK-{failure_method}",
        classroom=classroom,
    )
    db_session.add(student)
    db_session.flush()
    old_target = points["simple_linear_regression"].id
    old_prerequisite = points["descriptive_statistics"].id
    new_prerequisite = points["linear_algebra"].id
    path = LearningPath(
        student_id=student.id,
        target_knowledge_point_id=old_target,
        algorithm=MasteryAlgorithm.BKT,
        state=PathState.CURRENT,
        score=0.5,
        config_snapshot={},
    )
    db_session.add(path)
    db_session.commit()

    original_rollback = db_session.rollback
    rollback_calls = 0

    def tracked_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    original_flush = db_session.flush

    def fail_flush(*args: object, **kwargs: object) -> None:
        if db_session.deleted:
            raise RuntimeError("injected flush failure")
        original_flush(*args, **kwargs)

    def fail_commit() -> None:
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(db_session, "rollback", tracked_rollback)
    monkeypatch.setattr(
        db_session,
        failure_method,
        fail_flush if failure_method == "flush" else fail_commit,
    )

    with pytest.raises(RuntimeError, match=f"injected {failure_method} failure"):
        client.put(
            f"/api/v1/knowledge/prerequisites/{old_target}/{old_prerequisite}",
            json={"knowledge_point_id": old_target, "prerequisite_id": new_prerequisite},
        )

    assert rollback_calls == 1
    db_session.expire_all()
    assert db_session.get(Prerequisite, (old_target, old_prerequisite)) is not None
    assert db_session.get(Prerequisite, (old_target, new_prerequisite)) is None
    db_session.refresh(path)
    assert path.state == PathState.CURRENT
