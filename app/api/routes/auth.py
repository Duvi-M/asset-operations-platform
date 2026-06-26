import logging
import hmac

from fastapi import APIRouter, Depends, Header, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.models.user import User, UserRole
from app.schemas.auth import (
    BootstrapAdminRequest,
    BootstrapAdminResponse,
    DevUserDiagnosticRead,
    DevPasswordResetRequest,
    DevPasswordResetResponse,
    LoginRequest,
    LoginResponse,
    UserRead,
)
from app.services.exceptions import forbidden
from app.services import user_service, audit_service

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


def require_admin_or_dev_reset_token(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    dev_reset_token: str | None = Header(None, alias="X-Dev-Reset-Token"),
) -> User | None:
    if credentials and credentials.scheme.lower() == "bearer":
        try:
            payload = decode_access_token(credentials.credentials)
            user_id = int(payload.get("sub"))
            current_user = user_service.get_user_by_id(db, user_id)
        except (ValueError, TypeError):
            current_user = None
        if current_user and current_user.is_active and current_user.role == UserRole.ADMIN:
            return current_user

    if settings.dev_reset_token and dev_reset_token:
        if hmac.compare_digest(dev_reset_token, settings.dev_reset_token):
            return None

    raise forbidden("Se requiere admin JWT o X-Dev-Reset-Token válido.")


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


@router.post(
    "/dev/password-reset",
    response_model=DevPasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="TEMP DEV ONLY: resetear contraseña de usuario por email",
    description=(
        "Endpoint temporal para desarrollo/MVP. Requiere JWT de administrador. "
        "No devuelve ni registra la contraseña."
    ),
)
def dev_reset_password(
    data: DevPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = user_service.reset_user_password_by_email(
        db,
        email=data.email,
        new_password=data.new_password,
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="dev_password_reset",
        entity_type="user",
        entity_id=user.id,
        metadata={
            "target_email": user.email,
            "target_user_id": user.id,
            "temporary_endpoint": True,
        },
    )
    return DevPasswordResetResponse(
        message="Contraseña actualizada correctamente.",
        user_id=user.id,
        email=user.email,
    )


@router.get(
    "/dev/users",
    response_model=list[DevUserDiagnosticRead],
    status_code=status.HTTP_200_OK,
    summary="TEMP DEV ONLY: listar usuarios sin hashes de contraseña",
    description=(
        "Endpoint temporal para diagnosticar usuarios en producción. "
        "Requiere JWT admin o header X-Dev-Reset-Token si DEV_RESET_TOKEN está configurado."
    ),
)
def dev_list_users(
    db: Session = Depends(get_db),
    actor: User | None = Depends(require_admin_or_dev_reset_token),
):
    users = user_service.list_users(db)
    audit_service.log_action(
        user_id=actor.id if actor else None,
        action="dev_list_users",
        entity_type="user",
        metadata={
            "total": len(users),
            "auth_method": "admin_jwt" if actor else "dev_reset_token",
            "temporary_endpoint": True,
        },
    )
    return users


@router.get(
    "/me",
    response_model=UserRead,
    summary="Obtener el usuario autenticado",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
