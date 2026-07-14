from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, MasteryStatus
from app.models import MasteryResult, User
from app.services.diagnosis import (
    calculate_bkt_score,
    evaluate_algorithms,
    recompute_bkt_mastery,
    recompute_rule_mastery,
)
from app.services.simulation import seed_demo_data


def test_bkt_updates_with_ordered_evidence() -> None:
    initial, count = calculate_bkt_score([])
    after_correct, _ = calculate_bkt_score([True])
    after_three_correct, _ = calculate_bkt_score([True, True, True])
    after_incorrect, _ = calculate_bkt_score([False])

    assert initial == 0.2 and count == 0
    assert after_three_correct > after_correct > initial
    assert after_incorrect < after_correct


def test_bkt_recompute_and_evaluation(db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    recompute_rule_mastery(db_session)
    assert recompute_bkt_mastery(db_session) == 1250
    assert db_session.scalar(
        select(func.count()).select_from(MasteryResult).where(
            MasteryResult.algorithm == MasteryAlgorithm.BKT
        )
    ) == 1250

    evaluations = evaluate_algorithms(db_session)
    assert {item["algorithm"] for item in evaluations} == {"rule", "bkt"}
    assert all(item["sample_size"] == 1250 for item in evaluations)
    assert all(0 <= item["weak_f1"] <= 1 for item in evaluations)


def test_bkt_without_evidence_is_unknown(db_session: Session) -> None:
    seed_demo_data(db_session, export_dir=None)
    recompute_bkt_mastery(db_session)
    result = db_session.scalar(
        select(MasteryResult).where(
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
            MasteryResult.evidence_count == 0,
        )
    )
    assert result is not None
    assert result.score == 0.2
    assert result.status == MasteryStatus.UNKNOWN


def test_teacher_switches_algorithm_and_reads_evaluation(
    client: TestClient, db_session: Session
) -> None:
    seed_demo_data(db_session, export_dir=None)
    recompute_rule_mastery(db_session)
    recompute_bkt_mastery(db_session)
    teacher = db_session.scalar(select(User).where(User.username == "teacher01"))
    assert teacher is not None
    client.post(
        "/api/v1/auth/login",
        json={"username": teacher.username, "password": "Teacher@123456"},
    )

    selected = client.put("/api/v1/diagnosis/algorithm", json={"algorithm": "rule"})
    assert selected.status_code == 200
    assert client.get("/api/v1/diagnosis/algorithm").json()["algorithm"] == "rule"
    evaluation = client.get("/api/v1/diagnosis/evaluation")
    assert evaluation.status_code == 200
    assert len(evaluation.json()) == 2
