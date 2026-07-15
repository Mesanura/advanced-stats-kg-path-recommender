from datetime import datetime

from pydantic import BaseModel

from app.enums import AbilityDimension, MasteryAlgorithm, MasteryStatus


class MasteryItemRead(BaseModel):
    knowledge_point_id: int
    name: str
    chapter: str
    dimension: AbilityDimension
    difficulty: int
    score: float
    status: MasteryStatus
    evidence_count: int


class StudentDiagnosisRead(BaseModel):
    student_id: int
    student_no: str
    display_name: str
    algorithm: MasteryAlgorithm
    calculated_at: datetime
    items: list[MasteryItemRead]
    weak_points: list[str]
    suggested_directions: list[AbilityDimension]


class RecomputeResponse(BaseModel):
    algorithm: MasteryAlgorithm
    results_updated: int


class AlgorithmSelection(BaseModel):
    algorithm: MasteryAlgorithm


class AlgorithmEvaluation(BaseModel):
    algorithm: MasteryAlgorithm
    sample_size: int
    mae: float
    rmse: float
    spearman: float
    weak_precision: float
    weak_recall: float
    weak_f1: float
