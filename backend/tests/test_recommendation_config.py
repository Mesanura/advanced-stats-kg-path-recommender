from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathState
from app.models import KnowledgePoint, LearningPath, MasteryResult, StudentProfile, User
from app.services.diagnosis import recompute_bkt_mastery
from app.services.recommendation import recommend_path
from app.services.simulation import seed_demo_data


def login_teacher(client: TestClient, db: Session) -> None:
    teacher = db.scalar(select(User).where(User.username == "teacher01"))
    assert teacher is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": "Teacher@123456"},
    )


def test_config_update_marks_paths_stale(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    recompute_bkt_mastery(db_session)
    target = db_session.scalar(
        select(KnowledgePoint).where(KnowledgePoint.code == "support_vector_machine")
    )
    assert target is not None
    student_id = db_session.scalar(
        select(MasteryResult.student_id).where(
            MasteryResult.knowledge_point_id == target.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
            MasteryResult.score < 0.7,
        )
    )
    student = db_session.get(StudentProfile, student_id)
    assert student is not None
    path = recommend_path(db_session, student_id=student.id, target_id=target.id)
    login_teacher(client, db_session)

    payload = {
        "diagnostic_algorithm": "rule",
        "min_path_length": 4,
        "max_path_length": 7,
        "mastery_threshold": 0.75,
        "weak_threshold": 0.45,
        "weak_priority_weight": 0.5,
        "mastered_alignment_weight": 0.2,
        "length_penalty_weight": 0.15,
        "difficulty_jump_weight": 0.15,
    }
    response = client.put("/api/v1/teacher/recommendation-config", json=payload)
    assert response.status_code == 200
    assert response.json()["max_path_length"] == 7
    db_session.refresh(path)
    assert path.state == PathState.STALE


def test_config_rejects_invalid_weights(client: TestClient, db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    login_teacher(client, db_session)
    response = client.put(
        "/api/v1/teacher/recommendation-config",
        json={
            "diagnostic_algorithm": "bkt",
            "min_path_length": 8,
            "max_path_length": 5,
            "mastery_threshold": 0.5,
            "weak_threshold": 0.7,
            "weak_priority_weight": 0.1,
            "mastered_alignment_weight": 0.1,
            "length_penalty_weight": 0.1,
            "difficulty_jump_weight": 0.1,
        },
    )
    assert response.status_code == 422

