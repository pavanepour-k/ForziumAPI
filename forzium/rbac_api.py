"""HTTP endpoints for managing RBAC roles and assignments."""

from __future__ import annotations

import os
from typing import Any, Iterable

from .app import ForziumApp
from .middleware import JWTAuthMiddleware
from .security import (
    assign_role,
    define_role,
    delete_role,
    revoke_permission,
    get_audit_log,
    list_roles,
    list_user_roles,
    remove_role,
)

router = ForziumApp()
router.add_middleware(
    JWTAuthMiddleware,
    secret=os.getenv("FORZIUM_SECRET", "secret"),
    scopes=["rbac"],
)


@router.post("/roles")
def create_role(payload: dict[str, Any]) -> dict[str, str]:
    """Create a role with optional permissions."""

    name = payload.get("name", "")
    perms = payload.get("permissions", [])
    define_role(name, perms)
    return {"status": "ok"}


@router.get("/roles")
def get_roles() -> dict[str, Iterable[str]]:
    """List all defined roles."""

    return {"roles": list_roles()}


@router.delete("/roles")
def delete_role_endpoint(name: str) -> dict[str, str]:
    """Delete role *name* and its assignments."""

    delete_role(name)
    return {"status": "ok"}


@router.post("/assign")
def add_role(payload: dict[str, Any]) -> dict[str, str]:
    """Assign a role to a user."""

    assign_role(payload.get("user", ""), payload.get("role", ""))
    return {"status": "ok"}


@router.delete("/assign")
def delete_role_assignment(payload: dict[str, Any]) -> dict[str, str]:
    """Remove a role from a user."""

    remove_role(payload.get("user", ""), payload.get("role", ""))
    return {"status": "ok"}


@router.delete("/permissions")
def delete_permission(payload: dict[str, Any]) -> dict[str, str]:
    """Revoke a permission from a role."""

    revoke_permission(payload.get("role", ""), payload.get("permission", ""))
    return {"status": "ok"}


@router.get("/user-roles")
def user_roles(user: str) -> dict[str, Iterable[str]]:
    """Return roles assigned to *user*."""

    return {"roles": list_user_roles(user)}


@router.get("/audit-log")
def audit_log(filter_token: str | None = None) -> dict[str, Iterable[dict[str, Any]]]:
    """Return recorded token audit events filtered by *filter_token*."""

    return {"log": get_audit_log(filter_token)}


__all__ = ["router"]
