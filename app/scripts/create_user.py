import argparse
import getpass
import sys

from app.core.database import SessionLocal
from app.models.user import UserRole
from app.services.user_service import create_user


def prompt_password() -> str:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise ValueError("Las contraseñas no coinciden.")
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    return password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crear usuario para AssetOps.")
    parser.add_argument("--email", required=True, help="Email del usuario")
    parser.add_argument("--full-name", required=True, help="Nombre completo")
    parser.add_argument(
        "--role",
        choices=[UserRole.ADMIN.value, UserRole.TECHNICIAN.value],
        required=True,
        help="Rol del usuario",
    )
    parser.add_argument(
        "--password",
        help="Password del usuario. Si se omite, se pedirá de forma interactiva.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password or prompt_password()

    db = SessionLocal()
    try:
        user = create_user(
            db,
            email=args.email,
            full_name=args.full_name,
            password=password,
            role=UserRole(args.role),
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"Usuario creado: {user.email} ({user.role.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
