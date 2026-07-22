from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathState
from app.models import KnowledgePoint, LearningPath, MasteryResult, StudentProfile, User
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


def test_exercise_updates_mastery_and_regenerates_original_path(
    client: TestClient, db_session: Session
) -> None:
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
    feedback = response.json()
    assert feedback["mastery_score"] >= before_score
    assert feedback["paths_marked_stale"] == 1
    assert feedback["updated_path"]["id"] != path.id
    assert feedback["updated_path"]["target_knowledge_point_id"] == point.id
    assert feedback["updated_path"]["state"] == PathState.CURRENT
    db_session.refresh(path)
    assert path.state == PathState.STALE
    current_paths = list(
        db_session.scalars(
            select(LearningPath).where(
                LearningPath.student_id == student.id,
                LearningPath.state == PathState.CURRENT,
            )
        )
    )
    assert len(current_paths) == 1
    assert current_paths[0].id == feedback["updated_path"]["id"]
    assert current_paths[0].target_knowledge_point_id == path.target_knowledge_point_id

    repeated = client.post(
        "/api/v1/students/me/behavior/exercises",
        json={"knowledge_point_id": point.id, "is_correct": True},
    )
    assert repeated.status_code == 200
    repeated_path = repeated.json()["updated_path"]
    assert repeated_path["id"] != feedback["updated_path"]["id"]
    assert repeated_path["target_knowledge_point_id"] == path.target_knowledge_point_id


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
    assert visit.json()["updated_path"] is None
    assert video.json()["updated_path"] is None
