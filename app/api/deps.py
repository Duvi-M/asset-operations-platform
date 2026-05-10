from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.exceptions import forbidden, unauthorized
from app.services import user_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("Debes iniciar sesión.")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        raise unauthorized("Token inválido o expirado.")

    user = user_service.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise unauthorized("Usuario no válido o inactivo.")

    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed_roles = {role.value for role in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed_roles:
            raise forbidden()
        return current_user

    return dependency


def require_admin(current_user: User = Depends(require_roles(UserRole.ADMIN))) -> User:
    return current_user
