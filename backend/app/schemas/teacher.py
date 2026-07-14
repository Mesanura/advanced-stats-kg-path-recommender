from pydantic import BaseModel

from app.enums import AbilityDimension, MasteryAlgorithm


class ScopeClass(BaseModel):
    id: int
    name: str
    grade_id: int
    grade_name: str


class TeacherScope(BaseModel):
    classes: list[ScopeClass]


class StatusDistribution(BaseModel):
    unknown: int
    weak: int
    learning: int
    mastered: int


class KnowledgeStatistic(BaseModel):
    knowledge_point_id: int
    name: str
    average: float
    minimum: float
    maximum: float
    distribution: StatusDistribution


class DimensionStatistic(BaseModel):
    dimension: AbilityDimension
    average: float


class AttentionStudent(BaseModel):
    student_id: int
    student_no: str
    display_name: str
    classroom_name: str
    average: float
    weak_count: int


class TeacherOverview(BaseModel):
    algorithm: MasteryAlgorithm
    student_count: int
    average_mastery: float
    dimensions: list[DimensionStatistic]
    knowledge_points: list[KnowledgeStatistic]
    weak_top5: list[KnowledgeStatistic]
    attention_students: list[AttentionStudent]

