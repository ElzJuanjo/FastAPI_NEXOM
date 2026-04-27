from typing import List
from domain.entities.landing_page import LandingPage, LandingPageSection
from domain.entities.base import LandingPageStatus
from domain.repositories.landing_page_repository import LandingPageRepository


class LandingPageNotFoundError(Exception):
    pass

class LandingSectionNotFoundError(Exception):
    pass


class LandingPageCreate:
    def __init__(self, repo: LandingPageRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: str, name: str, brand_id: str | None = None, campaign: str | None = None, sections_data: list[dict] | None = None) -> LandingPage:
        lp = LandingPage(organization_id=org_id, brand_id=brand_id, name=name, campaign=campaign, status=LandingPageStatus.DRAFT)
        lp = await self._repo.create(lp)

        if sections_data:
            for s in sections_data:
                section = LandingPageSection(landing_page_id=lp.id, **s)
                await self._repo.add_section(section)

        return lp


class LandingPageList:
    def __init__(self, repo: LandingPageRepository) -> None:
        self._repo = repo

    async def execute(self, brand_id: str) -> List[LandingPage]:
        return await self._repo.list_by_brand(brand_id)


class LandingPageUpdate:
    def __init__(self, repo: LandingPageRepository) -> None:
        self._repo = repo

    async def execute(self, lp_id: str, **kwargs) -> LandingPage:
        from datetime import datetime, timezone
        lp = await self._repo.get_by_id(lp_id)
        if not lp:
            raise LandingPageNotFoundError(f"LandingPage {lp_id} no encontrada")
        nullable_fields = {"brand_id", "published_url", "seo_title", "seo_description", "og_image", "analytics_config", "custom_css"}
        for k, v in kwargs.items():
            if k in nullable_fields:
                setattr(lp, k, v)
            elif v is not None:
                setattr(lp, k, v)
        # Auto-stamp published_at when going to published
        if kwargs.get("status") in ("published", LandingPageStatus.PUBLISHED) and not lp.published_at:
            lp.published_at = datetime.now(timezone.utc)
        return await self._repo.update(lp)


class LandingPageDelete:
    def __init__(self, repo: LandingPageRepository) -> None:
        self._repo = repo

    async def execute(self, lp_id: str) -> None:
        lp = await self._repo.get_by_id(lp_id)
        if not lp:
            raise LandingPageNotFoundError(f"LandingPage {lp_id} no encontrada")
        await self._repo.soft_delete(lp_id)


class LandingSectionUpdate:
    def __init__(self, repo: LandingPageRepository) -> None:
        self._repo = repo

    async def execute(self, section_id: str, **kwargs) -> LandingPageSection:
        section = await self._repo.get_section_by_id(section_id)
        if not section:
            raise LandingSectionNotFoundError(f"Section {section_id} no encontrada")

        # Campos que permiten ser seteados a None explícitamente
        nullable_fields = {"image_url", "images", "cta_text", "cta_url", "content", "ab_group"}

        for k, v in kwargs.items():
            if k in nullable_fields:
                setattr(section, k, v)  # Permite None
            elif v is not None:
                setattr(section, k, v)

        return await self._repo.update_section(section)