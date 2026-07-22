from pydantic import BaseModel, Field

from app.enums import MasteryStatus
from app.schemas.recommendation import LearningPathRead


class VisitCreate(BaseModel):
    knowledge_point_id: int
    duration_seconds: int = Field(ge=1, le=7200)


class ExerciseCreate(BaseModel):
    knowledge_point_id: int
    is_correct: bool


class VideoProgressCreate(BaseModel):
    knowledge_point_id: int
    progress_percent: float = Field(ge=0, le=100)


class BehaviorFeedback(BaseModel):
    message: str
    knowledge_point_id: int
    mastery_score: float
    mastery_status: MasteryStatus
    paths_marked_stale: int
    updated_path: LearningPathRead | None = None
