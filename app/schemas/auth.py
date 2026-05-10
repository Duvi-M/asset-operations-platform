from datetime import datetime

from pydantic import Field

from app.models.user import UserRole
from app.schemas.base import AppModel


class LoginRequest(AppModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=200)


class BootstrapAdminRequest(AppModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=200)
    full_name: str = Field(..., min_length=1, max_length=255)


class BootstrapAdminResponse(AppModel):
    message: str


class UserRead(AppModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginResponse(AppModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
