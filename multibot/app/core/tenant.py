from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncGenerator

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

current_tenant_var: ContextVar = ContextVar("current_tenant", default=None)


def get_current_tenant():
    return current_tenant_var.get()


@asynccontextmanager
async def bind_tenant(tenant) -> AsyncGenerator:
    token = current_tenant_var.set(tenant)
    try:
        yield tenant
    finally:
        current_tenant_var.reset(token)


async def get_tenant_by_slug(slug: str, session: AsyncSession):
    from app.models.tenant import Tenant
    result = await session.execute(
        sa.select(Tenant).where(Tenant.slug == slug)
    )
    return result.scalar_one_or_none()


async def get_tenant_from_path(
    tenant_slug: str,
    session: AsyncSession = Depends(get_session),
):
    tenant = await get_tenant_by_slug(tenant_slug, session)
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")
    return tenant


async def get_tenant_from_request(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    slug = request.path_params.get("tenant_slug")
    if not slug:
        raise HTTPException(status_code=400, detail="tenant_slug missing from path")
    return await get_tenant_from_path(slug, session)
