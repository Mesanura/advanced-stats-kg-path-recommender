from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.enums import AbilityDimension, MasteryAlgorithm, Role
from app.models import (
    Classroom,
    ExerciseAttempt,
    Grade,
    KnowledgePoint,
    KnowledgeVisit,
    LatentMastery,
    Prerequisite,
    RecommendationConfig,
    StudentProfile,
    TeacherClass,
    User,
    VideoProgress,
)
from app.security import hash_password
from app.services.knowledge import import_default_graph

DEFAULT_SEED = 20260713
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "seed" / "generated"


@dataclass
class SeedSummary:
    grades: int
    classrooms: int
    students: int
    knowledge_points: int
    visits: int
    exercise_attempts: int
    video_records: int


def _clear_domain_data(db: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.commit()


def _existing_summary(db: Session) -> SeedSummary:
    return SeedSummary(
        grades=db.scalar(select(func.count()).select_from(Grade)) or 0,
        classrooms=db.scalar(select(func.count()).select_from(Classroom)) or 0,
        students=db.scalar(select(func.count()).select_from(StudentProfile)) or 0,
        knowledge_points=db.scalar(select(func.count()).select_from(KnowledgePoint)) or 0,
        visits=db.scalar(select(func.count()).select_from(KnowledgeVisit)) or 0,
        exercise_attempts=db.scalar(select(func.count()).select_from(ExerciseAttempt)) or 0,
        video_records=db.scalar(select(func.count()).select_from(VideoProgress)) or 0,
    )


def _knowledge_order(db: Session, points: list[KnowledgePoint]) -> list[int]:
    graph = nx.DiGraph()
    graph.add_nodes_from(point.id for point in points)
    graph.add_edges_from(
        (edge.prerequisite_id, edge.knowledge_point_id) for edge in db.scalars(select(Prerequisite))
    )
    return list(nx.topological_sort(graph))


def seed_demo_data(
    db: Session,
    *,
    reset: bool = False,
    seed: int = DEFAULT_SEED,
    export_dir: Path | None = DEFAULT_EXPORT_DIR,
) -> SeedSummary:
    existing = _existing_summary(db)
    if existing.students and not reset:
        return existing
    if reset:
        _clear_domain_data(db)

    rng = np.random.default_rng(seed)
    import_default_graph(db)
    points = list(db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)))
    point_by_id = {point.id: point for point in points}
    point_order = _knowledge_order(db, points)
    prerequisites: dict[int, list[int]] = {point.id: [] for point in points}
    for edge in db.scalars(select(Prerequisite)):
        prerequisites[edge.knowledge_point_id].append(edge.prerequisite_id)

    grade = Grade(name="2026级")
    classes = [Classroom(name="高级统计01班", grade=grade), Classroom(name="高级统计02班", grade=grade)]
    db.add(grade)
    admin = User(
        username="admin",
        display_name="系统管理员",
        role=Role.ADMIN,
        password_hash=hash_password("Admin@123456"),
    )
    teachers = [
        User(
            username=f"teacher{index:02d}",
            display_name=f"教师{index:02d}",
            role=Role.TEACHER,
            password_hash=hash_password("Teacher@123456"),
        )
        for index in (1, 2)
    ]
    db.add_all([admin, *teachers])
    db.flush()
    for teacher, classroom in zip(teachers, classes, strict=True):
        teacher.teacher_assignments.append(TeacherClass(classroom=classroom))

    db.add(
        RecommendationConfig(
            id=1,
            diagnostic_algorithm=MasteryAlgorithm.BKT,
            min_path_length=5,
            max_path_length=8,
        )
    )

    student_rows: list[dict[str, object]] = []
    visit_rows: list[dict[str, object]] = []
    exercise_rows: list[dict[str, object]] = []
    video_rows: list[dict[str, object]] = []
    latent_rows: list[dict[str, object]] = []
    profile_names = ["high"] * 15 + ["medium"] * 25 + ["struggling"] * 10
    rng.shuffle(profile_names)
    profile_base = {"high": 0.82, "medium": 0.61, "struggling": 0.40}
    start = datetime(2026, 2, 17, 8, tzinfo=UTC)

    for index in range(1, 51):
        profile_name = profile_names[index - 1]
        classroom = classes[0 if index <= 25 else 1]
        user = User(
            username=f"2026{index:04d}",
            display_name=f"学生{index:02d}",
            role=Role.STUDENT,
            password_hash=hash_password("Student@123456"),
        )
        profile = StudentProfile(
            user=user,
            student_no=f"2026{index:04d}",
            classroom=classroom,
        )
        db.add(profile)
        db.flush()
        student_rows.append(
            {
                "student_no": profile.student_no,
                "display_name": user.display_name,
                "classroom": classroom.name,
                "ability_profile": profile_name,
            }
        )

        dimension_offsets = {
            dimension: float(rng.normal(0, 0.07)) for dimension in AbilityDimension
        }
        mastery: dict[int, float] = {}
        for point_id in point_order:
            point = point_by_id[point_id]
            prereq_scores = [mastery[item] for item in prerequisites[point_id]]
            prereq_effect = (float(np.mean(prereq_scores)) - 0.5) * 0.18 if prereq_scores else 0
            score = np.clip(
                profile_base[profile_name]
                + dimension_offsets[point.dimension]
                - 0.055 * (point.difficulty - 1)
                + prereq_effect
                + rng.normal(0, 0.055),
                0.06,
                0.97,
            )
            mastery[point_id] = float(score)
            db.add(LatentMastery(student_id=profile.id, knowledge_point_id=point_id, score=float(score)))
            latent_rows.append(
                {
                    "student_no": profile.student_no,
                    "knowledge_code": point.code,
                    "latent_mastery": round(float(score), 6),
                }
            )

        point_ids = np.array([point.id for point in points])
        deficits = np.array([1.08 - mastery[point.id] for point in points])
        visit_weights = deficits / deficits.sum()
        visit_count = int(rng.integers(40, 61))
        for sequence in range(visit_count):
            point_id = int(rng.choice(point_ids, p=visit_weights))
            event_time = start + timedelta(minutes=int(rng.integers(0, 120 * 24 * 60)))
            duration = int(np.clip(rng.normal(260 + (1 - mastery[point_id]) * 520, 150), 60, 1800))
            db.add(
                KnowledgeVisit(
                    student_id=profile.id,
                    knowledge_point_id=point_id,
                    visited_at=event_time,
                    duration_seconds=duration,
                )
            )
            visit_rows.append(
                {
                    "student_no": profile.student_no,
                    "knowledge_code": point_by_id[point_id].code,
                    "visited_at": event_time.isoformat(),
                    "duration_seconds": duration,
                    "sequence": sequence + 1,
                }
            )

        exercise_count = int(rng.integers(30, 46))
        exercise_weights = np.array([0.6 + point.difficulty * 0.12 for point in points])
        exercise_weights /= exercise_weights.sum()
        for sequence in range(exercise_count):
            point_id = int(rng.choice(point_ids, p=exercise_weights))
            event_time = start + timedelta(minutes=int(rng.integers(0, 120 * 24 * 60)))
            correct_probability = float(np.clip(0.04 + 0.92 * mastery[point_id], 0.05, 0.95))
            is_correct = bool(rng.random() < correct_probability)
            db.add(
                ExerciseAttempt(
                    student_id=profile.id,
                    knowledge_point_id=point_id,
                    attempted_at=event_time,
                    is_correct=is_correct,
                )
            )
            exercise_rows.append(
                {
                    "student_no": profile.student_no,
                    "knowledge_code": point_by_id[point_id].code,
                    "attempted_at": event_time.isoformat(),
                    "is_correct": is_correct,
                    "sequence": sequence + 1,
                }
            )

        video_count = int(rng.integers(12, 26))
        video_point_ids = rng.choice(point_ids, size=video_count, replace=False)
        for point_id_raw in video_point_ids:
            point_id = int(point_id_raw)
            progress = float(np.clip(rng.normal(38 + mastery[point_id] * 58, 15), 5, 100))
            db.add(
                VideoProgress(
                    student_id=profile.id,
                    knowledge_point_id=point_id,
                    progress_percent=progress,
                )
            )
            video_rows.append(
                {
                    "student_no": profile.student_no,
                    "knowledge_code": point_by_id[point_id].code,
                    "progress_percent": round(progress, 2),
                }
            )

    db.commit()

    if export_dir is not None:
        export_dir.mkdir(parents=True, exist_ok=True)
        frames = {
            "students.csv": student_rows,
            "knowledge_visits.csv": visit_rows,
            "exercise_attempts.csv": exercise_rows,
            "video_progress.csv": video_rows,
            "latent_mastery.csv": latent_rows,
        }
        for filename, rows in frames.items():
            pd.DataFrame(rows).to_csv(export_dir / filename, index=False, encoding="utf-8-sig")

    return _existing_summary(db)


def summary_dict(summary: SeedSummary) -> dict[str, int]:
    return {key: int(value) for key, value in asdict(summary).items()}

