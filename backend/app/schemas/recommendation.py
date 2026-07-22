from datetime import datetime

from pydantic import BaseModel

from app.enums import (
    MasteryAlgorithm,
    MasteryStatus,
    PathLengthException,
    PathNodeStatus,
    PathState,
)


class RecommendationRequest(BaseModel):
    target_knowledge_point_id: int


class PathNodeRead(BaseModel):
    sequence: int
    stage: int
    knowledge_point_id: int
    name: str
    difficulty: int
    resource_url: str
    prerequisites: list[str]
    status: PathNodeStatus
    mastery_score: float


class DependencyGraphNodeRead(BaseModel):
    knowledge_point_id: int
    name: str
    difficulty: int
    resource_url: str
    prerequisites: list[str]
    is_active: bool
    mastery_score: float
    mastery_status: MasteryStatus
    in_recommended_path: bool
    is_target: bool


class DependencyGraphEdgeRead(BaseModel):
    prerequisite_id: int
    knowledge_point_id: int


class DependencyGraphRead(BaseModel):
    nodes: list[DependencyGraphNodeRead]
    edges: list[DependencyGraphEdgeRead]


class LearningPathRead(BaseModel):
    id: int
    student_id: int
    target_knowledge_point_id: int
    target_name: str
    algorithm: MasteryAlgorithm
    state: PathState
    score: float
    stage_count: int
    length_exception: PathLengthException | None
    created_at: datetime
    nodes: list[PathNodeRead]
    dependency_graph: DependencyGraphRead
