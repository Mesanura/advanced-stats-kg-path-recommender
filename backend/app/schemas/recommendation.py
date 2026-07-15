from datetime import datetime

from pydantic import BaseModel

from app.enums import MasteryAlgorithm, PathLengthException, PathNodeStatus, PathState


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
