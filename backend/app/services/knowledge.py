from pathlib import Path

import networkx as nx
import yaml
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.enums import AbilityDimension, PathState
from app.models import KnowledgePoint, LearningPath, Prerequisite

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GRAPH_PATH = PROJECT_ROOT / "data" / "seed" / "knowledge_graph.yaml"


def build_graph(db: Session) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(db.scalars(select(KnowledgePoint.id)))
    graph.add_edges_from(
        (item.prerequisite_id, item.knowledge_point_id) for item in db.scalars(select(Prerequisite))
    )
    return graph


def would_create_cycle(db: Session, prerequisite_id: int, knowledge_point_id: int) -> bool:
    graph = build_graph(db)
    graph.add_edge(prerequisite_id, knowledge_point_id)
    return not nx.is_directed_acyclic_graph(graph)


def mark_paths_stale(db: Session) -> None:
    db.execute(
        update(LearningPath)
        .where(LearningPath.state == PathState.CURRENT)
        .values(state=PathState.STALE)
    )


def import_default_graph(db: Session, path: Path = DEFAULT_GRAPH_PATH) -> tuple[int, int]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    existing = {item.code: item for item in db.scalars(select(KnowledgePoint))}
    created_points = 0
    for raw in data["knowledge_points"]:
        point = existing.get(raw["code"])
        if point is None:
            point = KnowledgePoint(
                code=raw["code"],
                name=raw["name"],
                chapter=raw["chapter"],
                dimension=AbilityDimension(raw["dimension"]),
                difficulty=raw["difficulty"],
                resource_url=raw["resource_url"],
                description=raw.get("description"),
            )
            db.add(point)
            existing[point.code] = point
            created_points += 1
    db.flush()

    existing_edges = {
        (item.prerequisite_id, item.knowledge_point_id) for item in db.scalars(select(Prerequisite))
    }
    created_edges = 0
    for prerequisite_code, target_code in data["prerequisites"]:
        edge = (existing[prerequisite_code].id, existing[target_code].id)
        if edge not in existing_edges:
            db.add(Prerequisite(prerequisite_id=edge[0], knowledge_point_id=edge[1]))
            existing_edges.add(edge)
            created_edges += 1
    db.commit()
    return created_points, created_edges

