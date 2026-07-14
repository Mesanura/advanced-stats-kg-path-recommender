from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathState
from app.models import KnowledgePoint, MasteryResult, StudentProfile, User
from app.services.diagnosis import recompute_bkt_mastery
from app.services.recommendation import recommend_path
from app.services.simulation import seed_demo_data


def setup_student(client: TestClient, db: Session) -> tuple[StudentProfile, KnowledgePoint]:
    seed_demo_data(db, export_dir=None)
    recompute_bkt_mastery(db)
    point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.code == "support_vector_machine"))
    assert point is not None
    student_id = db.scalar(
        select(MasteryResult.student_id).where(
            MasteryResult.knowledge_point_id == point.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
            MasteryResult.score < 0.7,
        )
    )
    student = db.get(StudentProfile, student_id)
    assert student is not None
    user = db.get(User, student.user_id)
    assert user is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Student@123456"},
    )
    return student, point


def test_exercise_updates_mastery_and_stales_path(client: TestClient, db_session: Session) -> None:
    student, point = setup_student(client, db_session)
    path = recommend_path(db_session, student_id=student.id, target_id=point.id)
    before = db_session.scalar(
        select(MasteryResult).where(
            MasteryResult.student_id == student.id,
            MasteryResult.knowledge_point_id == point.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
        )
    )
    assert before is not None
    before_score = before.score

    response = client.post(
        "/api/v1/students/me/behavior/exercises",
        json={"knowledge_point_id": point.id, "is_correct": True},
    )
    assert response.status_code == 200
    assert response.json()["mastery_score"] >= before_score
    db_session.refresh(path)
    assert path.state == PathState.STALE


def test_visit_and_video_progress_are_recorded(client: TestClient, db_session: Session) -> None:
    _, point = setup_student(client, db_session)
    visit = client.post(
        "/api/v1/students/me/behavior/visits",
        json={"knowledge_point_id": point.id, "duration_seconds": 600},
    )
    video = client.put(
        "/api/v1/students/me/behavior/video-progress",
        json={"knowledge_point_id": point.id, "progress_percent": 80},
    )
    assert visit.status_code == 200
    assert video.status_code == 200

