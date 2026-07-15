from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.enums import AbilityDimension


class KnowledgePointBase(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=100)
    chapter: str = Field(min_length=2, max_length=100)
    dimension: AbilityDimension
    difficulty: int = Field(ge=1, le=5)
    resource_url: HttpUrl
    description: str | None = None


class KnowledgePointCreate(KnowledgePointBase):
    pass


class KnowledgePointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    chapter: str | None = Field(default=None, min_length=2, max_length=100)
    dimension: AbilityDimension | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    resource_url: HttpUrl | None = None
    description: str | None = None
    is_active: bool | None = None


class KnowledgePointRead(KnowledgePointBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PrerequisiteCreate(BaseModel):
    knowledge_point_id: int
    prerequisite_id: int


class PrerequisiteUpdate(PrerequisiteCreate):
    pass


class PrerequisiteRead(PrerequisiteCreate):
    knowledge_point_name: str
    prerequisite_name: str


class GraphResponse(BaseModel):
    nodes: list[KnowledgePointRead]
    edges: list[PrerequisiteRead]


class ImportResponse(BaseModel):
    knowledge_points_created: int
    prerequisites_created: int
