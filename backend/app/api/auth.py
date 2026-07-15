from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_current_user
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse, MessageResponse, SessionResponse, UserMe
from app.security import COOKIE_NAME, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(user.id, user.role),
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )
    return LoginResponse(user=UserMe.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    response.delete_cookie(COOKIE_NAME, path="/")
    return MessageResponse(message="已退出登录")


@router.get("/session", response_model=SessionResponse)
def session(user: User | None = Depends(get_optional_current_user)) -> SessionResponse:
    return SessionResponse(user=UserMe.model_validate(user) if user else None)


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)) -> UserMe:
    return UserMe.model_validate(user)
