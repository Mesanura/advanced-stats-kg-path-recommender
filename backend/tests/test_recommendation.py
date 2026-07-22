from time import perf_counter

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathLengthException, PathState
from app.models import (
    KnowledgePoint,
    LearningPath,
    MasteryResult,
    Prerequisite,
    RecommendationConfig,
    StudentProfile,
    User,
)
from app.services.diagnosis import recompute_bkt_mastery
from app.services.recommendation import recommend_path
from app.services.simulation import seed_demo_data


def setup_data(db: Session) -> StudentProfile:
    seed_demo_data(db, export_dir=None)
    recompute_bkt_mastery(db)
    student = db.scalar(select(StudentProfile).order_by(StudentProfile.id))
    assert student is not None
    return student


def point_by_code(db: Session, code: str) -> KnowledgePoint:
    point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.code == code))
    assert point is not None
    return point


def set_mastery(db: Session, student_id: int, *, default: float, overrides: dict[int, float] | None = None) -> None:
    overrides = overrides or {}
    results = db.scalars(
        select(MasteryResult).where(
            MasteryResult.student_id == student_id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
        )
    )
    for result in results:
        result.score = overrides.get(result.knowledge_point_id, default)
    db.commit()


def graph_from_db(db: Session) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(db.scalars(select(KnowledgePoint.id)))
    graph.add_edges_from(
        (edge.prerequisite_id, edge.knowledge_point_id)
        for edge in db.scalars(select(Prerequisite))
    )
    return graph


def assert_topological_plan(db: Session, path: LearningPath) -> None:
    position = {item.knowledge_point_id: item.sequence for item in path.items}
    closure = nx.transitive_closure_dag(graph_from_db(db))
    assert all(
        position[source] < position[target]
        for source, target in closure.edges
        if source in position and target in position
    )


def test_all_required_svm_plan_has_eight_nodes(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "support_vector_machine")
    set_mastery(db_session, student.id, default=0.2)

    started = perf_counter()
    path = recommend_path(db_session, student_id=student.id, target_id=target.id)
    elapsed = perf_counter() - started

    graph = graph_from_db(db_session)
    expected = nx.ancestors(graph, target.id) | {target.id}
    assert {item.knowledge_point_id for item in path.items} == expected
    assert len(path.items) == 8
    assert {item.stage for item in path.items} == {1}
    assert path.items[-1].knowledge_point_id == target.id
    assert path.length_exception is None
    assert_topological_plan(db_session, path)
    assert elapsed < 0.5


def test_long_dependency_plan_is_balanced_into_stages(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "roc_auc")
    set_mastery(db_session, student.id, default=0.2)

    path = recommend_path(db_session, student_id=student.id, target_id=target.id)

    counts = [sum(item.stage == stage for item in path.items) for stage in range(1, 4)]
    assert len(path.items) == 19
    assert counts == [7, 6, 6]
    assert path.length_exception == PathLengthException.STAGED_DEPENDENCY
    assert path.items[-1].knowledge_point_id == target.id
    assert_topological_plan(db_session, path)


def test_maximum_stage_length_changes_stage_partition(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "roc_auc")
    set_mastery(db_session, student.id, default=0.2)

    default_path = recommend_path(db_session, student_id=student.id, target_id=target.id)
    config = db_session.get(RecommendationConfig, 1)
    assert config is not None
    config.max_path_length = 5
    db_session.commit()
    shorter_stages = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert max(item.stage for item in default_path.items) == 3
    assert max(item.stage for item in shorter_stages.items) == 4
    assert [sum(item.stage == stage for item in shorter_stages.items) for stage in range(1, 5)] == [5, 5, 5, 4]


def test_mastered_ancestors_are_omitted_but_transitive_order_is_kept(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "roc_auc")
    root = point_by_code(db_session, "descriptive_statistics")
    set_mastery(db_session, student.id, default=0.9, overrides={root.id: 0.3, target.id: 0.3})

    path = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert [item.knowledge_point_id for item in path.items] == [root.id, target.id]
    assert path.length_exception == PathLengthException.SHALLOW_TARGET


def test_inactive_intermediate_keeps_active_ancestor_in_transitive_order(
    db_session: Session,
) -> None:
    student = setup_data(db_session)
    root = point_by_code(db_session, "descriptive_statistics")
    middle = point_by_code(db_session, "simple_linear_regression")
    target = point_by_code(db_session, "multiple_linear_regression")
    middle.is_active = False
    db_session.commit()
    set_mastery(
        db_session,
        student.id,
        default=0.9,
        overrides={root.id: 0.2, target.id: 0.2},
    )

    path = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert [item.knowledge_point_id for item in path.items] == [root.id, target.id]
    assert middle.id not in {item.knowledge_point_id for item in path.items}
    assert_topological_plan(db_session, path)


def test_missing_mastery_key_defaults_to_point_two(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "support_vector_machine")
    unknown = point_by_code(db_session, "linear_algebra")
    set_mastery(db_session, student.id, default=0.9, overrides={target.id: 0.2})
    missing_result = db_session.scalar(
        select(MasteryResult).where(
            MasteryResult.student_id == student.id,
            MasteryResult.algorithm == MasteryAlgorithm.BKT,
            MasteryResult.knowledge_point_id == unknown.id,
        )
    )
    assert missing_result is not None
    db_session.delete(missing_result)
    db_session.commit()

    path = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert [item.knowledge_point_id for item in path.items] == [unknown.id, target.id]
    unknown_item = next(item for item in path.items if item.knowledge_point_id == unknown.id)
    assert unknown_item.mastery_score == pytest.approx(0.2)


def test_weakness_priority_cannot_be_offset_by_alignment(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "classification_metrics")
    weaker = point_by_code(db_session, "logistic_regression")
    better_aligned = point_by_code(db_session, "decision_tree")
    generalized = point_by_code(db_session, "generalized_linear_model")
    hypothesis = point_by_code(db_session, "hypothesis_testing")
    set_mastery(
        db_session,
        student.id,
        default=0.9,
        overrides={
            target.id: 0.2,
            weaker.id: 0.49,
            better_aligned.id: 0.5,
            generalized.id: 0.7,
            hypothesis.id: 0.7,
        },
    )

    path = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert [item.knowledge_point_id for item in path.items] == [
        weaker.id,
        better_aligned.id,
        target.id,
    ]


def test_config_weights_change_ready_node_order(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "support_vector_machine")
    descriptive = point_by_code(db_session, "descriptive_statistics")
    linear_algebra = point_by_code(db_session, "linear_algebra")
    set_mastery(
        db_session,
        student.id,
        default=0.9,
        overrides={target.id: 0.2, descriptive.id: 0.49, linear_algebra.id: 0.1},
    )

    weak_first = recommend_path(db_session, student_id=student.id, target_id=target.id)
    config = db_session.get(RecommendationConfig, 1)
    assert config is not None
    config.weak_priority_weight = 0.0
    config.mastered_alignment_weight = 0.85
    config.length_penalty_weight = 0.1
    config.difficulty_jump_weight = 0.05
    db_session.commit()
    stable_difficulty_first = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert weak_first.items[0].knowledge_point_id == linear_algebra.id
    assert stable_difficulty_first.items[0].knowledge_point_id == descriptive.id
    assert weak_first.score != stable_difficulty_first.score


def test_new_path_marks_previous_stale(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "support_vector_machine")
    first = recommend_path(db_session, student_id=student.id, target_id=target.id)
    second = recommend_path(db_session, student_id=student.id, target_id=target.id)
    db_session.refresh(first)

    assert first.state == PathState.STALE
    assert second.state == PathState.CURRENT


def test_mastered_target_returns_single_node(db_session: Session) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "support_vector_machine")
    set_mastery(db_session, student.id, default=0.9)

    default_path = recommend_path(db_session, student_id=student.id, target_id=target.id)
    config = db_session.get(RecommendationConfig, 1)
    assert config is not None
    config.weak_priority_weight = 0.55
    config.mastered_alignment_weight = 0.15
    db_session.commit()
    reweighted_path = recommend_path(db_session, student_id=student.id, target_id=target.id)

    assert len(default_path.items) == 1
    assert default_path.items[0].stage == 1
    assert default_path.length_exception == PathLengthException.TARGET_MASTERED
    assert default_path.score == pytest.approx(0.27)
    assert reweighted_path.score == pytest.approx(0.19)


def test_student_recommendation_api_returns_stage_contract(
    client: TestClient, db_session: Session
) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "roc_auc")
    set_mastery(db_session, student.id, default=0.2)
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
    payload = response.json()
    assert payload["stage_count"] == 3
    assert payload["length_exception"] == "staged_dependency"
    assert max(item["stage"] for item in payload["nodes"]) == 3

    graph = graph_from_db(db_session)
    expected_ids = nx.ancestors(graph, target.id) | {target.id}
    dependency_graph = payload["dependency_graph"]
    assert {item["knowledge_point_id"] for item in dependency_graph["nodes"]} == expected_ids
    assert {
        (item["prerequisite_id"], item["knowledge_point_id"])
        for item in dependency_graph["edges"]
    } == set(graph.subgraph(expected_ids).edges)
    assert next(
        item for item in dependency_graph["nodes"] if item["knowledge_point_id"] == target.id
    )["is_target"] is True

    saved = client.get("/api/v1/recommendations/me")
    assert saved.status_code == 200
    assert saved.json()[0]["dependency_graph"] == dependency_graph


def test_dependency_graph_keeps_mastered_and_inactive_ancestors(
    client: TestClient, db_session: Session
) -> None:
    student = setup_data(db_session)
    target = point_by_code(db_session, "roc_auc")
    ancestor = point_by_code(db_session, "descriptive_statistics")
    set_mastery(db_session, student.id, default=0.2, overrides={ancestor.id: 0.9})
    ancestor.is_active = False
    db_session.commit()
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
    payload = response.json()
    path_ids = {item["knowledge_point_id"] for item in payload["nodes"]}
    graph_node = next(
        item
        for item in payload["dependency_graph"]["nodes"]
        if item["knowledge_point_id"] == ancestor.id
    )
    assert ancestor.id not in path_ids
    assert graph_node["is_active"] is False
    assert graph_node["in_recommended_path"] is False
    assert graph_node["mastery_score"] == pytest.approx(0.9)
