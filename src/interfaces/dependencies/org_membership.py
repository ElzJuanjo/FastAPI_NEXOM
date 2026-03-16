"""
Dependency que valida que el usuario autenticado pertenece a la organización.
Usar en todos los endpoints que operan sobre recursos de una organización.
"""

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config.database import get_session
from domain.entities.organization import OrganizationMember
from interfaces.dependencies.auth_dependencies import get_current_user_id


async def verify_org_membership(
    org_id: str = Query(..., description="Organization ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> str:
    """
    Verifica que el usuario autenticado es miembro de la organización.
    Retorna el org_id si es válido, lanza 403 si no.
    """
    stmt = select(OrganizationMember.id).where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id,
        OrganizationMember.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta organización.",
        )

    return org_id


async def verify_org_owner(
    org_id: str = Query(..., description="Organization ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> str:
    """
    Verifica que el usuario es OWNER de la organización.
    Para acciones administrativas (cambiar plan, eliminar org, etc.)
    """
    stmt = select(OrganizationMember.id).where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id,
        OrganizationMember.is_owner.is_(True),
        OrganizationMember.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    owner = result.scalar_one_or_none()

    if not owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el owner de la organización puede realizar esta acción.",
        )

    return org_id


async def verify_product_access(
    product_id: str = Query(..., description="Product ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> str:
    """Verifica que el usuario tiene acceso al producto via su organización."""
    from domain.entities.product import Product

    stmt = (
        select(OrganizationMember.id)
        .join(Product, Product.organization_id == OrganizationMember.organization_id)
        .where(
            Product.id == product_id,
            Product.deleted_at.is_(None),
            OrganizationMember.user_id == user_id,
            OrganizationMember.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este producto.",
        )
    return product_id


async def verify_brand_access(
    brand_id: str = Query(..., description="Brand ID"),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> str:
    """Verifica que el usuario tiene acceso a la marca via su organización."""
    from domain.entities.brand import Brand

    stmt = (
        select(OrganizationMember.id)
        .join(Brand, Brand.organization_id == OrganizationMember.organization_id)
        .where(
            Brand.id == brand_id,
            Brand.deleted_at.is_(None),
            OrganizationMember.user_id == user_id,
            OrganizationMember.deleted_at.is_(None),
        )
    )
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta marca.",
        )
    return brand_id


async def verify_org_membership_path(
    org_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> str:
    """
    Igual que verify_org_membership pero para endpoints donde
    org_id viene como path param (/{org_id}/...) en vez de query param.
    """
    stmt = select(OrganizationMember.id).where(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id,
        OrganizationMember.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta organización.",
        )

    return org_id