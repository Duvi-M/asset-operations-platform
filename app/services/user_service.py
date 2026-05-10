import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.services.exceptions import bad_request, service_unavailable, unauthorized

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    try:
        return db.query(User).filter(User.email == normalize_email(email)).first()
    except SQLAlchemyError:
        logger.exception("Database error getting user by email")
        raise service_unavailable("No fue posible consultar el usuario en este momento.")


def get_user_by_id(db: Session, user_id: int) -> User | None:
    try:
        return db.get(User, user_id)
    except SQLAlchemyError:
        logger.exception("Database error getting user by id", extra={"user_id": user_id})
        raise service_unavailable("No fue posible consultar el usuario en este momento.")


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        logger.warning("Login failed", extra={"email": normalize_email(email)})
        raise unauthorized("Credenciales inválidas.")

    if not user.is_active:
        logger.warning("Inactive user login attempt", extra={"user_id": user.id, "email": user.email})
        raise unauthorized("Usuario inactivo.")

    logger.info("Login successful", extra={"user_id": user.id, "email": user.email, "role": user.role.value})
    return user


def create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    normalized_email = normalize_email(email)
    if get_user_by_email(db, normalized_email):
        raise bad_request("Ya existe un usuario con ese email.")

    user = User(
        email=normalized_email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating user", extra={"email": normalized_email, "role": role.value})
        raise service_unavailable("No fue posible crear el usuario en este momento.")

    logger.info("User created", extra={"user_id": user.id, "email": user.email, "role": user.role.value})
    return user
