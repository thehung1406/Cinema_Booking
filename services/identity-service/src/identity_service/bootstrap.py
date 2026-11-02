"""Interactive, operator-only initialization of a genuinely empty Identity store."""

from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from .config import Settings
from .models import Permission, Role, RolePermission, User
from .schemas import EmployeeCreate
from .tokens import passwords

PERMISSIONS = {
    "tickets.check_in",
    "reviews.moderate",
    "seat_types.manage",
    "users.manage",
    "roles.manage",
    "films.manage",
    "rooms.manage",
    "showtimes.manage",
    "knowledge.manage",
    "reports.view",
    "notifications.manage",
}
STAFF = {"tickets.check_in", "reviews.moderate", "seat_types.manage"}
MANAGER = STAFF | {"films.manage", "rooms.manage", "showtimes.manage"}


def initialize(engine, body):
    # Validate without ever printing submitted credentials in a ValidationError.
    try:
        body = EmployeeCreate.model_validate({**body, "role_id": 1})
    except ValidationError:
        raise ValueError(
            "Invalid account fields (password: 8–72 UTF-8 bytes)"
        ) from None
    with Session(engine) as db, db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(8117402)"))
        # Also blocks concurrent public registration during first initialization.
        db.execute(
            text(
                "LOCK TABLE users, roles, permissions, role_permissions IN EXCLUSIVE MODE"
            )
        )
        if any(
            db.scalar(select(func.count()).select_from(table))
            for table in (User, Role, Permission, RolePermission)
        ):
            raise RuntimeError(
                "Identity is not empty; bootstrap refuses to change existing accounts or RBAC"
            )
        roles = {
            code: Role(code=code, name=code)
            for code in ("USER", "STAFF", "MANAGER", "ADMIN")
        }
        permissions = {
            code: Permission(code=code, name=code) for code in sorted(PERMISSIONS)
        }
        db.add_all([*roles.values(), *permissions.values()])
        db.flush()
        for code, allowed in {
            "ADMIN": PERMISSIONS,
            "MANAGER": MANAGER,
            "STAFF": STAFF,
        }.items():
            db.add_all(
                RolePermission(role_id=roles[code].id, permission_id=permissions[p].id)
                for p in sorted(allowed)
            )
        db.add(
            User(
                username=body.username,
                email=str(body.email),
                full_name=body.full_name,
                phone=body.phone,
                role_id=roles["ADMIN"].id,
                password=passwords.hash(body.password),
            )
        )


def main():
    body = {
        "username": input("Admin username: "),
        "email": input("Admin email: "),
        "full_name": input("Admin full name: "),
        "password": getpass("Admin password: "),
    }
    if body["password"] != getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    engine = create_engine(Settings().database_url)
    try:
        initialize(engine, body)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
    finally:
        engine.dispose()
    print("Empty Identity store initialized. Sign in through the normal API.")


if __name__ == "__main__":
    main()
