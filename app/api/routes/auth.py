import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.schemas.auth import (
    BootstrapAdminRequest,
    BootstrapAdminResponse,
    LoginRequest,
    LoginResponse,
    UserRead,
)
from app.services.exceptions import forbidden
from app.services import user_service, audit_service

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post(
    "/bootstrap-admin",
    response_model=BootstrapAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear el primer usuario administrador",
)
def bootstrap_admin(data: BootstrapAdminRequest, db: Session = Depends(get_db)):
    db.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
    user_count = db.query(User).count()
    if user_count != 0:
        logger.warning(
            "Bootstrap admin blocked because users already exist",
            extra={"user_count": user_count, "email": user_service.normalize_email(data.email)},
        )
        raise forbidden("El bootstrap de administrador solo está permitido cuando no existen usuarios.")

    user = user_service.create_user(
        db,
        email=data.email,
        full_name=data.full_name,
        password=data.password,
        role=UserRole.ADMIN,
    )
    logger.info(
        "Bootstrap admin created",
        extra={"user_id": user.id, "email": user.email},
    )
    return BootstrapAdminResponse(message="Administrador inicial creado correctamente.")


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = user_service.authenticate_user(db, data.email, data.password)
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    audit_service.log_action(
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=user.id,
        metadata={"email": user.email, "role": user.role.value},
    )
    return LoginResponse(access_token=token, user=UserRead.model_validate(user))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Obtener el usuario autenticado",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
