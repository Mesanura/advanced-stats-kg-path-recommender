from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db import get_db
from app.enums import AbilityDimension, Role
from app.models import KnowledgePoint, Prerequisite, User
from app.schemas.auth import MessageResponse
from app.schemas.knowledge import (
    GraphResponse,
    ImportResponse,
    KnowledgePointCreate,
    KnowledgePointRead,
    KnowledgePointUpdate,
    PrerequisiteCreate,
    PrerequisiteRead,
    PrerequisiteUpdate,
)
from app.services.knowledge import import_default_graph, mark_paths_stale, would_create_cycle

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
editor = require_roles(Role.TEACHER, Role.ADMIN)


def point_or_404(db: Session, point_id: int) -> KnowledgePoint:
    point = db.get(KnowledgePoint, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识点不存在")
    return point


@router.get("/points", response_model=list[KnowledgePointRead])
def list_points(
    chapter: str | None = None,
    difficulty: int | None = Query(default=None, ge=1, le=5),
    dimension: AbilityDimension | None = None,
    query: str | None = Query(default=None, max_length=100),
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KnowledgePoint]:
    del user
    statement = select(KnowledgePoint)
    if chapter:
        statement = statement.where(KnowledgePoint.chapter == chapter)
    if difficulty:
        statement = statement.where(KnowledgePoint.difficulty == difficulty)
    if dimension:
        statement = statement.where(KnowledgePoint.dimension == dimension)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(KnowledgePoint.name.ilike(pattern), KnowledgePoint.code.ilike(pattern))
        )
    if active_only:
        statement = statement.where(KnowledgePoint.is_active.is_(True))
    return list(db.scalars(statement.order_by(KnowledgePoint.chapter, KnowledgePoint.id)))


@router.post("/points", response_model=KnowledgePointRead, status_code=status.HTTP_201_CREATED)
def create_point(
    payload: KnowledgePointCreate,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> KnowledgePoint:
    del user
    if db.scalar(
        select(KnowledgePoint).where(
            or_(KnowledgePoint.code == payload.code, KnowledgePoint.name == payload.name)
        )
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="知识点编码或名称已存在")
    point = KnowledgePoint(**payload.model_dump(mode="json"))
    db.add(point)
    db.commit()
    return point


@router.patch("/points/{point_id}", response_model=KnowledgePointRead)
def update_point(
    point_id: int,
    payload: KnowledgePointUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> KnowledgePoint:
    del user
    point = point_or_404(db, point_id)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if "name" in changes and db.scalar(
        select(KnowledgePoint.id).where(
            KnowledgePoint.name == changes["name"],
            KnowledgePoint.id != point_id,
        )
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="知识点名称已存在")
    for key, value in changes.items():
        setattr(point, key, value)
    mark_paths_stale(db)
    db.commit()
    return point


@router.delete("/points/{point_id}", response_model=MessageResponse)
def delete_point(
    point_id: int,
    confirm: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> MessageResponse:
    del user
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="删除知识点需要显式确认")
    point = point_or_404(db, point_id)
    mark_paths_stale(db)
    db.delete(point)
    db.commit()
    return MessageResponse(message="知识点及其关联数据已删除")


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> GraphResponse:
    del user
    points = list(db.scalars(select(KnowledgePoint).order_by(KnowledgePoint.id)))
    point_map = {item.id: item for item in points}
    edges = list(db.scalars(select(Prerequisite)))
    return GraphResponse(
        nodes=[KnowledgePointRead.model_validate(item) for item in points],
        edges=[
            PrerequisiteRead(
                knowledge_point_id=item.knowledge_point_id,
                prerequisite_id=item.prerequisite_id,
                knowledge_point_name=point_map[item.knowledge_point_id].name,
                prerequisite_name=point_map[item.prerequisite_id].name,
            )
            for item in edges
        ],
    )


@router.post("/prerequisites", response_model=PrerequisiteRead, status_code=status.HTTP_201_CREATED)
def create_prerequisite(
    payload: PrerequisiteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> PrerequisiteRead:
    del user
    target = point_or_404(db, payload.knowledge_point_id)
    prerequisite = point_or_404(db, payload.prerequisite_id)
    if target.id == prerequisite.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="知识点不能依赖自身")
    if db.get(Prerequisite, (target.id, prerequisite.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="前置关系已存在")
    if would_create_cycle(db, prerequisite.id, target.id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该关系会形成循环依赖")
    edge = Prerequisite(knowledge_point_id=target.id, prerequisite_id=prerequisite.id)
    db.add(edge)
    mark_paths_stale(db)
    db.commit()
    return PrerequisiteRead(
        **payload.model_dump(),
        knowledge_point_name=target.name,
        prerequisite_name=prerequisite.name,
    )


@router.put(
    "/prerequisites/{knowledge_point_id}/{prerequisite_id}",
    response_model=PrerequisiteRead,
)
def update_prerequisite(
    knowledge_point_id: int,
    prerequisite_id: int,
    payload: PrerequisiteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> PrerequisiteRead:
    del user
    current = db.get(Prerequisite, (knowledge_point_id, prerequisite_id))
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="前置关系不存在")
    target = point_or_404(db, payload.knowledge_point_id)
    prerequisite = point_or_404(db, payload.prerequisite_id)
    if target.id == prerequisite.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="知识点不能依赖自身")
    new_key = (target.id, prerequisite.id)
    old_key = (knowledge_point_id, prerequisite_id)
    if new_key != old_key and db.get(Prerequisite, new_key):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="前置关系已存在")
    if would_create_cycle(
        db,
        prerequisite.id,
        target.id,
        removed_edge=(prerequisite_id, knowledge_point_id),
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该关系会形成循环依赖")
    if new_key != old_key:
        try:
            db.delete(current)
            db.flush()
            db.add(Prerequisite(knowledge_point_id=target.id, prerequisite_id=prerequisite.id))
            mark_paths_stale(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return PrerequisiteRead(
        **payload.model_dump(),
        knowledge_point_name=target.name,
        prerequisite_name=prerequisite.name,
    )


@router.delete("/prerequisites/{knowledge_point_id}/{prerequisite_id}", response_model=MessageResponse)
def delete_prerequisite(
    knowledge_point_id: int,
    prerequisite_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(editor),
) -> MessageResponse:
    del user
    edge = db.get(Prerequisite, (knowledge_point_id, prerequisite_id))
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="前置关系不存在")
    db.delete(edge)
    mark_paths_stale(db)
    db.commit()
    return MessageResponse(message="前置关系已删除")


@router.post("/import-defaults", response_model=ImportResponse)
def import_defaults(
    db: Session = Depends(get_db), user: User = Depends(editor)
) -> ImportResponse:
    del user
    points, edges = import_default_graph(db)
    return ImportResponse(knowledge_points_created=points, prerequisites_created=edges)
