from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ExerciseAttempt, KnowledgeVisit, StudentProfile, VideoProgress
from app.services.simulation import seed_demo_data


def test_seed_meets_required_scale(db_session: Session) -> None:
    summary = seed_demo_data(db_session, export_dir=None)

    assert summary.grades == 1
    assert summary.classrooms == 2
    assert summary.students == 50
    assert summary.knowledge_points == 25
    assert summary.visits >= 50 * 40
    assert summary.exercise_attempts >= 50 * 30
    assert summary.video_records >= 50 * 12

    visit_counts = Counter(db_session.scalars(select(KnowledgeVisit.student_id)))
    exercise_counts = Counter(db_session.scalars(select(ExerciseAttempt.student_id)))
    video_counts = Counter(db_session.scalars(select(VideoProgress.student_id)))
    assert min(visit_counts.values()) >= 40
    assert min(exercise_counts.values()) >= 30
    assert min(video_counts.values()) >= 12


def test_seed_is_idempotent_without_reset(db_session: Session) -> None:
    first = seed_demo_data(db_session, export_dir=None)
    second = seed_demo_data(db_session, export_dir=None)

    assert first == second
    assert db_session.scalar(select(func.count()).select_from(StudentProfile)) == 50

