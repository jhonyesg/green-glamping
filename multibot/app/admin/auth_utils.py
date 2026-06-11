"""Authorization helpers for admin routes."""

from fastapi import Request


def effective_tenant(request: Request, requested: str) -> str:
    """
    Returns the tenant slug the current user is allowed to operate on.
    Client users are always locked to their own tenant; superadmins
    get whatever they requested.
    """
    if request.session.get("role") == "client":
        return request.session.get("tenant_slug") or requested
    return requested


def is_superadmin(request: Request) -> bool:
    return request.session.get("role") == "superadmin"
