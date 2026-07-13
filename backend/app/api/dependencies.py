from collections.abc import Callable

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.enums import Role
from app.models import User
from app.security import COOKIE_NAME, decode_access_token


def get_current_user(
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录状态无效或已过期",
    )
    if not token:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        user_id = int(str(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise credentials_error from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = set(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行此操作")
        return user

    return dependency

