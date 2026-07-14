from pydantic import BaseModel

from app.enums import AbilityDimension, MasteryAlgorithm
from app.schemas.diagnosis import MasteryItemRead
from app.schemas.knowledge import KnowledgePointRead
from app.schemas.recommendation import LearningPathRead


class DimensionMastery(BaseModel):
    dimension: AbilityDimension
    average: float


class StudentDashboard(BaseModel):
    student_id: int
    student_no: str
    display_name: str
    classroom_name: str
    algorithm: MasteryAlgorithm
    average_mastery: float
    dimensions: list[DimensionMastery]
    mastery_items: list[MasteryItemRead]
    weak_points: list[str]
    suggested_directions: list[str]
    available_targets: list[KnowledgePointRead]
    current_paths: list[LearningPathRead]

