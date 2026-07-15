from dataclasses import asdict, dataclass
from math import ceil

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MasteryAlgorithm, PathLengthException, PathNodeStatus, PathState
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
    graph: nx.DiGraph,
    stage_count: int,
    weights: RecommendationWeights,
) -> float:
    scores = [mastery.get(point_id, 0.2) for point_id in path]
    weak_coverage = sum(1 - score for score in scores) / len(scores)
    alignments = []
    for point_id in path:
        prerequisites = list(graph.predecessors(point_id))
        alignments.append(
            sum(mastery.get(item, 0.2) for item in prerequisites) / len(prerequisites)
            if prerequisites
            else 1.0
        )
    alignment = sum(alignments) / len(alignments)
    stage_penalty = (stage_count - 1) / stage_count
    jumps = [
        abs(points[current].difficulty - points[previous].difficulty) / 4
        for previous, current in zip(path, path[1:])
    ]
    difficulty_jump = sum(jumps) / len(jumps) if jumps else 0
    score = (
        weights.weak_priority * weak_coverage
        + weights.mastered_alignment * alignment
        - weights.length_penalty * stage_penalty
        - weights.difficulty_jump * difficulty_jump
    )
    return round(float(score), 6)


def _build_graph(db: Session, point_ids: set[int]) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(point_ids)
    graph.add_edges_from(
        (edge.prerequisite_id, edge.knowledge_point_id)
        for edge in db.scalars(select(Prerequisite))
        if edge.prerequisite_id in point_ids and edge.knowledge_point_id in point_ids
    )
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("知识图谱存在循环依赖")
    return graph


def _ordered_required_nodes(
    graph: nx.DiGraph,
    *,
    target_id: int,
    mastery: dict[int, float],
    mastery_threshold: float,
    points: dict[int, KnowledgePoint],
    weights: RecommendationWeights,
) -> list[int]:
    required = {
        point_id
        for point_id in nx.ancestors(graph, target_id)
        if point_id in points and mastery.get(point_id, 0.2) < mastery_threshold
    }
    required.add(target_id)
    precedence = nx.transitive_closure_dag(graph).subgraph(required).copy()
    indegree = dict(precedence.in_degree())
    ready = {point_id for point_id, degree in indegree.items() if degree == 0}
    ordered: list[int] = []

    while ready:
        candidates = ready - {target_id} if len(ordered) < len(required) - 1 else ready
        if not candidates:
            candidates = ready
        previous_id = ordered[-1] if ordered else None

        def priority(point_id: int) -> tuple[float, float, float, int, int]:
            prerequisites = list(graph.predecessors(point_id))
            alignment = (
                sum(mastery.get(item, 0.2) for item in prerequisites) / len(prerequisites)
                if prerequisites
                else 1.0
            )
            difficulty_jump = (
                abs(points[point_id].difficulty - points[previous_id].difficulty) / 4
                if previous_id is not None
                else 0.0
            )
            return (
                weights.weak_priority * (1 - mastery.get(point_id, 0.2)),
                weights.mastered_alignment * alignment,
                -weights.difficulty_jump * difficulty_jump,
                -points[point_id].difficulty,
                -point_id,
            )

        current = max(candidates, key=priority)
        ready.remove(current)
        ordered.append(current)
        for successor in precedence.successors(current):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.add(successor)

    if len(ordered) != len(required):
        raise ValueError("无法生成满足全部前置关系的学习计划")
    return ordered


def _balanced_stages(total: int, maximum: int) -> tuple[list[int], int]:
    stage_count = max(1, ceil(total / maximum))
    base, remainder = divmod(total, stage_count)
    sizes = [base + (1 if index < remainder else 0) for index in range(stage_count)]
    stages: list[int] = []
    for stage, size in enumerate(sizes, start=1):
        stages.extend([stage] * size)
    return stages, stage_count


def recommend_path(db: Session, *, student_id: int, target_id: int) -> LearningPath:
    all_points = {item.id: item for item in db.scalars(select(KnowledgePoint))}
    points = {point_id: item for point_id, item in all_points.items() if item.is_active}
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
    graph = _build_graph(db, set(all_points))
    length_exception: PathLengthException | None = None
    if mastery.get(target_id, 0.2) >= config.mastery_threshold:
        selected = [target_id]
        stages = [1]
        stage_count = 1
        length_exception = PathLengthException.TARGET_MASTERED
    else:
        selected = _ordered_required_nodes(
            graph,
            target_id=target_id,
            mastery=mastery,
            mastery_threshold=config.mastery_threshold,
            points=points,
            weights=weights,
        )
        stages, stage_count = _balanced_stages(len(selected), config.max_path_length)
        if len(selected) < config.min_path_length:
            length_exception = PathLengthException.SHALLOW_TARGET
        elif stage_count > 1:
            length_exception = PathLengthException.STAGED_DEPENDENCY
    path_score = _score_path(selected, mastery, points, graph, stage_count, weights)

    snapshot = {
        "min_path_length": config.min_path_length,
        "max_path_length": config.max_path_length,
        "mastery_threshold": config.mastery_threshold,
        "dependency_policy": "all_required",
        "stage_count": stage_count,
        "weights": asdict(weights),
    }
    learning_path = LearningPath(
        student_id=student_id,
        target_knowledge_point_id=target_id,
        algorithm=algorithm,
        state=PathState.CURRENT,
        score=path_score,
        length_exception=length_exception.value if length_exception else None,
        config_snapshot=snapshot,
    )
    for sequence, (point_id, stage) in enumerate(zip(selected, stages, strict=True), start=1):
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
                stage=stage,
                knowledge_point_id=point_id,
                status=node_status,
                mastery_score=score,
            )
        )
    db.add(learning_path)
    db.commit()
    db.refresh(learning_path)
    return learning_path
