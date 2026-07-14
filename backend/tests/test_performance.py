import json
from statistics import quantiles
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm
from app.models import KnowledgePoint, MasteryResult, StudentProfile, User
from app.services.diagnosis import recompute_bkt_mastery, recompute_rule_mastery
from app.services.recommendation import recommend_path
from app.services.simulation import seed_demo_data


def test_full_diagnosis_and_dashboard_latency(
    client: TestClient,
    db_session: Session,
) -> None:
    seed_demo_data(db_session, export_dir=None)

    started = perf_counter()
    assert recompute_rule_mastery(db_session) == 1250
    rule_seconds = perf_counter() - started
    assert rule_seconds < 5

    started = perf_counter()
    assert recompute_bkt_mastery(db_session) == 1250
    bkt_seconds = perf_counter() - started
    assert bkt_seconds < 5

    student = db_session.scalar(select(User).where(User.username == '20260001'))
    assert student is not None
    login = client.post(
        '/api/v1/auth/login',
        json={'username': student.username, 'password': 'Student@123456'},
    )
    assert login.status_code == 200

    timings: list[float] = []
    for _ in range(20):
        started = perf_counter()
        response = client.get('/api/v1/students/me/dashboard')
        timings.append(perf_counter() - started)
        assert response.status_code == 200

    p95 = quantiles(timings, n=100, method='inclusive')[94]
    assert p95 < 0.3

    target = db_session.scalar(
        select(KnowledgePoint).where(KnowledgePoint.code == 'support_vector_machine')
    )
    assert target is not None
    path_student_id = db_session.scalar(
        select(MasteryResult.student_id)
        .where(
            MasteryResult.knowledge_point_id == target.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
            MasteryResult.score < 0.7,
        )
        .order_by(MasteryResult.student_id)
    )
    path_student = db_session.get(StudentProfile, path_student_id)
    assert path_student is not None
    started = perf_counter()
    recommend_path(db_session, student_id=path_student.id, target_id=target.id)
    path_seconds = perf_counter() - started
    assert path_seconds < 0.5

    print(
        json.dumps(
            {
                'rule_diagnosis_ms': round(rule_seconds * 1000, 3),
                'bkt_diagnosis_ms': round(bkt_seconds * 1000, 3),
                'dashboard_p95_ms': round(p95 * 1000, 3),
                'path_generation_ms': round(path_seconds * 1000, 3),
            },
            ensure_ascii=False,
        )
    )
