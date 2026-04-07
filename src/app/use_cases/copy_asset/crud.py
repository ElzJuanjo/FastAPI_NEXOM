"""
Casos de uso CRUD para CopyAsset.
"""

from typing import List

from domain.entities.copy_asset import CopyAsset
from domain.entities.base import CopyType, AdPlatform, AssetStatus
from domain.repositories.copy_asset_repository import CopyAssetRepository


class CopyAssetNotFoundError(Exception):
    pass


class CopyAssetCreate:

    def __init__(self, repo: CopyAssetRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: str, **kwargs) -> CopyAsset:
        # Convertir strings a Enums
        if "copy_type" in kwargs and isinstance(kwargs["copy_type"], str):
            try:
                kwargs["copy_type"] = CopyType(kwargs["copy_type"])
            except (ValueError, KeyError):
                pass

        if "platform" in kwargs and isinstance(kwargs["platform"], str):
            try:
                kwargs["platform"] = AdPlatform(kwargs["platform"])
            except (ValueError, KeyError):
                kwargs["platform"] = None

        if "status" in kwargs and isinstance(kwargs["status"], str):
            try:
                kwargs["status"] = AssetStatus(kwargs["status"])
            except (ValueError, KeyError):
                kwargs["status"] = AssetStatus.DRAFT

        asset = CopyAsset(
            organization_id=org_id,
            **kwargs,
        )
        return await self._repo.create(asset)


class CopyAssetList:

    def __init__(self, repo: CopyAssetRepository) -> None:
        self._repo = repo

    async def execute(
        self, org_id: str,
        copy_type: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        brand_id: str | None = None,
    ) -> List[CopyAsset]:
        return await self._repo.list_by_organization(org_id, copy_type, platform, status, brand_id)


class CopyAssetUpdate:

    def __init__(self, repo: CopyAssetRepository) -> None:
        self._repo = repo

    async def execute(self, asset_id: str, **kwargs) -> CopyAsset:
        asset = await self._repo.get_by_id(asset_id)
        if not asset:
            raise CopyAssetNotFoundError(f"CopyAsset {asset_id} no encontrado")

        # Campos que aceptan None explícito (para desasignar)
        nullable_fields = {"brand_id", "product_id", "platform", "tone", "variations"}

        # Mapeo de campos enum: string → Enum
        enum_map = {
            "copy_type": CopyType,
            "platform": AdPlatform,
            "status": AssetStatus,
        }

        for key, value in kwargs.items():
            # Convertir string vacío a None para campos nullables
            if key in nullable_fields and value == "":
                value = None

            # Convertir strings a Enums donde corresponda
            if key in enum_map and value is not None:
                try:
                    value = enum_map[key](value)
                except (ValueError, KeyError):
                    # Para campos nullables, un enum inválido se convierte en None
                    # Para campos requeridos, se mantiene el valor actual del asset
                    if key in nullable_fields:
                        value = None
                    else:
                        continue  # skip — no sobrescribir con un valor inválido

            if key in nullable_fields:
                setattr(asset, key, value)
            elif value is not None:
                setattr(asset, key, value)

        return await self._repo.update(asset)


class CopyAssetDelete:

    def __init__(self, repo: CopyAssetRepository) -> None:
        self._repo = repo

    async def execute(self, asset_id: str) -> None:
        asset = await self._repo.get_by_id(asset_id)
        if not asset:
            raise CopyAssetNotFoundError(f"CopyAsset {asset_id} no encontrado")
        await self._repo.delete(asset_id)