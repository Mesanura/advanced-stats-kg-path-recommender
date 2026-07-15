from pydantic import BaseModel, ConfigDict, Field

from app.enums import Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class UserMe(BaseModel):
    id: int
    username: str
    display_name: str
    role: Role

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    user: UserMe


class SessionResponse(BaseModel):
    user: UserMe | None


class MessageResponse(BaseModel):
    message: str
