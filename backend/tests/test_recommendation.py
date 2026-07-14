from time import perf_counter

import networkx as nx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathState
from app.models import KnowledgePoint, LearningPath, MasteryResult, Prerequisite, StudentProfile, User
from app.services.diagnosis import recompute_bkt_mastery
from app.services.recommendation import recommend_path
from app.services.simulation import seed_demo_data


def setup_data(db: Session) -> tuple[StudentProfile, KnowledgePoint]:
    seed_demo_data(db, export_dir=None)
    recompute_bkt_mastery(db)
    target = db.scalar(select(KnowledgePoint).where(KnowledgePoint.code == "support_vector_machine"))
    assert target is not None
    student_id = db.scalar(
        select(MasteryResult.student_id)
        .where(
            MasteryResult.knowledge_point_id == target.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
            MasteryResult.score < 0.7,
        )
        .order_by(MasteryResult.student_id)
    )
    student = db.get(StudentProfile, student_id)
    assert student is not None
    return student, target


def test_recommendation_is_valid_and_within_length(db_session: Session) -> None:
    student, target = setup_data(db_session)
    started = perf_counter()
    path = recommend_path(db_session, student_id=student.id, target_id=target.id)
    elapsed = perf_counter() - started

    assert 5 <= len(path.items) <= 8
    assert path.items[-1].knowledge_point_id == target.id
    graph = nx.DiGraph(
        (edge.prerequisite_id, edge.knowledge_point_id)
        for edge in db_session.scalars(select(Prerequisite))
    )
    assert all(
        graph.has_edge(previous.knowledge_point_id, current.knowledge_point_id)
        for previous, current in zip(path.items, path.items[1:])
    )
    assert elapsed < 0.5


def test_new_path_marks_previous_stale(db_session: Session) -> None:
    student, target = setup_data(db_session)
    first = recommend_path(db_session, student_id=student.id, target_id=target.id)
    second = recommend_path(db_session, student_id=student.id, target_id=target.id)
    db_session.refresh(first)

    assert first.state == PathState.STALE
    assert second.state == PathState.CURRENT


def test_mastered_target_returns_single_node(db_session: Session) -> None:
    student, target = setup_data(db_session)
    result = db_session.scalar(
        select(MasteryResult).where(
            MasteryResult.student_id == student.id,
            MasteryResult.knowledge_point_id == target.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
        )
    )
    assert result is not None
    result.score = 0.9
    db_session.commit()

    path = recommend_path(db_session, student_id=student.id, target_id=target.id)
    assert len(path.items) == 1
    assert path.length_exception == "target_mastered"


def test_student_recommendation_api(client: TestClient, db_session: Session) -> None:
    student, target = setup_data(db_session)
    user = db_session.get(User, student.user_id)
    assert user is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Student@123456"},
    )
    response = client.post(
        "/api/v1/recommendations/me",
        json={"target_knowledge_point_id": target.id},
    )

    assert response.status_code == 200
    assert 5 <= len(response.json()["nodes"]) <= 8
    assert client.get("/api/v1/recommendations/me").status_code == 200
