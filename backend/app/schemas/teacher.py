from pydantic import BaseModel, Field, model_validator

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


class RecommendationConfigPayload(BaseModel):
    diagnostic_algorithm: MasteryAlgorithm
    min_path_length: int = Field(ge=1, le=12)
    max_path_length: int = Field(ge=1, le=12)
    mastery_threshold: float = Field(ge=0, le=1)
    weak_threshold: float = Field(ge=0, le=1)
    weak_priority_weight: float = Field(ge=0, le=1)
    mastered_alignment_weight: float = Field(ge=0, le=1)
    length_penalty_weight: float = Field(ge=0, le=1)
    difficulty_jump_weight: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_config(self) -> "RecommendationConfigPayload":
        if self.max_path_length < self.min_path_length:
            raise ValueError("最大路径长度不能小于最短路径长度")
        if self.weak_threshold >= self.mastery_threshold:
            raise ValueError("薄弱阈值必须小于掌握阈值")
        total = (
            self.weak_priority_weight
            + self.mastered_alignment_weight
            + self.length_penalty_weight
            + self.difficulty_jump_weight
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError("四项推荐权重之和必须为 1")
        return self


class RecommendationConfigRead(RecommendationConfigPayload):
    id: int
