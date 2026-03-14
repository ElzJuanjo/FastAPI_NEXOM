from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from domain.entities.conversion import ConversionAnalysis, OptimizationRecommendation
from domain.repositories.conversion_repository import ConversionRepository


class ConversionSQLAlchemyRepository(ConversionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_analysis_by_id(self, analysis_id: str) -> Optional[ConversionAnalysis]:
        stmt = select(ConversionAnalysis).options(selectinload(ConversionAnalysis.recommendations)).where(ConversionAnalysis.id == analysis_id, ConversionAnalysis.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_analyses_by_brand(self, brand_id: str) -> List[ConversionAnalysis]:
        stmt = select(ConversionAnalysis).options(selectinload(ConversionAnalysis.recommendations)).where(ConversionAnalysis.brand_id == brand_id, ConversionAnalysis.deleted_at.is_(None)).order_by(ConversionAnalysis.analyzed_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_analysis(self, analysis: ConversionAnalysis) -> ConversionAnalysis:
        self._session.add(analysis)
        await self._session.flush()
        return analysis

    async def add_recommendation(self, rec: OptimizationRecommendation) -> OptimizationRecommendation:
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def update_recommendation(self, rec: OptimizationRecommendation) -> OptimizationRecommendation:
        await self._session.flush()
        return rec

    async def get_recommendation_by_id(self, rec_id: str) -> Optional[OptimizationRecommendation]:
        stmt = select(OptimizationRecommendation).where(OptimizationRecommendation.id == rec_id, OptimizationRecommendation.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()