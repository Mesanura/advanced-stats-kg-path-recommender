from dataclasses import asdict, dataclass

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathNodeStatus, PathState
from app.models import (
    KnowledgePoint,
    LearningPath,
    LearningPathItem,
    MasteryResult,
    Prerequisite,
    RecommendationConfig,
)
from app.services.diagnosis import recompute_bkt_mastery, recompute_rule_mastery


@dataclass
class RecommendationWeights:
    weak_priority: float
    mastered_alignment: float
    length_penalty: float
    difficulty_jump: float


def _mastery_map(
    db: Session, student_id: int, algorithm: MasteryAlgorithm
) -> dict[int, float]:
    results = list(
        db.scalars(
            select(MasteryResult).where(
                MasteryResult.student_id == student_id,
                MasteryResult.algorithm == algorithm,
            )
        )
    )
    if not results:
        updater = recompute_rule_mastery if algorithm == MasteryAlgorithm.RULE else recompute_bkt_mastery
        updater(db, [student_id])
        results = list(
            db.scalars(
                select(MasteryResult).where(
                    MasteryResult.student_id == student_id,
                    MasteryResult.algorithm == algorithm,
                )
            )
        )
    return {item.knowledge_point_id: item.score for item in results}


def _score_path(
    path: list[int],
    mastery: dict[int, float],
    points: dict[int, KnowledgePoint],
    max_length: int,
    weights: RecommendationWeights,
) -> float:
    scores = [mastery.get(point_id, 0.2) for point_id in path]
    weak_coverage = sum(1 - score for score in scores) / len(scores)
    alignment = sum(scores) / len(scores)
    length = len(path) / max_length
    jumps = [
        max(0, points[current].difficulty - points[previous].difficulty - 1) / 4
        for previous, current in zip(path, path[1:])
    ]
    difficulty_jump = sum(jumps) / len(jumps) if jumps else 0
    score = (
        weights.weak_priority * weak_coverage
        + weights.mastered_alignment * alignment
        - weights.length_penalty * length
        - weights.difficulty_jump * difficulty_jump
    )
    return round(float(score), 6)


def recommend_path(db: Session, *, student_id: int, target_id: int) -> LearningPath:
    points = {item.id: item for item in db.scalars(select(KnowledgePoint).where(KnowledgePoint.is_active.is_(True)))}
    if target_id not in points:
        raise ValueError("目标知识点不存在或已停用")
    config = db.get(RecommendationConfig, 1)
    if config is None:
        config = RecommendationConfig(id=1)
        db.add(config)
        db.flush()
    algorithm = config.diagnostic_algorithm
    mastery = _mastery_map(db, student_id, algorithm)

    for old_path in db.scalars(
        select(LearningPath).where(
            LearningPath.student_id == student_id,
            LearningPath.target_knowledge_point_id == target_id,
            LearningPath.state == PathState.CURRENT,
        )
    ):
        old_path.state = PathState.STALE

    weights = RecommendationWeights(
        weak_priority=config.weak_priority_weight,
        mastered_alignment=config.mastered_alignment_weight,
        length_penalty=config.length_penalty_weight,
        difficulty_jump=config.difficulty_jump_weight,
    )
    length_exception: str | None = None
    if mastery.get(target_id, 0.2) >= config.mastery_threshold:
        selected = [target_id]
        path_score = 1.0
        length_exception = "target_mastered"
    else:
        graph = nx.DiGraph()
        graph.add_nodes_from(points)
        graph.add_edges_from(
            (edge.prerequisite_id, edge.knowledge_point_id)
            for edge in db.scalars(select(Prerequisite))
            if edge.prerequisite_id in points and edge.knowledge_point_id in points
        )
        roots = [node for node in graph if graph.in_degree(node) == 0]
        candidates: list[list[int]] = []
        for root in roots:
            if nx.has_path(graph, root, target_id):
                candidates.extend(
                    list(nx.all_simple_paths(graph, root, target_id, cutoff=config.max_path_length - 1))
                )
        preferred = [
            path for path in candidates if config.min_path_length <= len(path) <= config.max_path_length
        ]
        if preferred:
            candidates = preferred
        elif candidates:
            length_exception = "shallow_target"
        else:
            raise ValueError("目标知识点不存在有效前置路径")
        scored = [
            (
                _score_path(path, mastery, points, config.max_path_length, weights),
                path,
            )
            for path in candidates
        ]
        path_score, selected = max(scored, key=lambda item: (item[0], -len(item[1])))

    snapshot = {
        "min_path_length": config.min_path_length,
        "max_path_length": config.max_path_length,
        "mastery_threshold": config.mastery_threshold,
        "weights": asdict(weights),
    }
    learning_path = LearningPath(
        student_id=student_id,
        target_knowledge_point_id=target_id,
        algorithm=algorithm,
        state=PathState.CURRENT,
        score=path_score,
        length_exception=length_exception,
        config_snapshot=snapshot,
    )
    for sequence, point_id in enumerate(selected, start=1):
        score = mastery.get(point_id, 0.2)
        if point_id == target_id:
            node_status = PathNodeStatus.TARGET
        elif score >= config.mastery_threshold:
            node_status = PathNodeStatus.MASTERED
        else:
            node_status = PathNodeStatus.RECOMMENDED
        learning_path.items.append(
            LearningPathItem(
                sequence=sequence,
                knowledge_point_id=point_id,
                status=node_status,
                mastery_score=score,
            )
        )
    db.add(learning_path)
    db.commit()
    db.refresh(learning_path)
    return learning_path
