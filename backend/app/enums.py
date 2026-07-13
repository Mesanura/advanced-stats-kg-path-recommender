from enum import StrEnum


class Role(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class AbilityDimension(StrEnum):
    STATISTICS_FOUNDATION = "statistics_foundation"
    LINEAR_MODELS = "linear_models"
    SELECTION_REGULARIZATION = "selection_regularization"
    CLASSIFICATION = "classification"
    EVALUATION_ENSEMBLE = "evaluation_ensemble"


class MasteryAlgorithm(StrEnum):
    RULE = "rule"
    BKT = "bkt"


class MasteryStatus(StrEnum):
    UNKNOWN = "unknown"
    WEAK = "weak"
    LEARNING = "learning"
    MASTERED = "mastered"


class PathNodeStatus(StrEnum):
    MASTERED = "mastered"
    RECOMMENDED = "recommended"
    TARGET = "target"


class PathState(StrEnum):
    CURRENT = "current"
    STALE = "stale"

