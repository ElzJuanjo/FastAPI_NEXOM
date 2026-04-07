"""
Caso de uso: Seed de planes iniciales.
Idempotente — solo crea planes que no existan por plan_type.
"""

from domain.entities.plan import Plan
from domain.entities.base import PlanType
from domain.repositories.plan_repository import PlanRepository

SEED_PLANS = [
    {
        "name": "Free",
        "plan_type": PlanType.FREE,
        "max_credits_per_month": 100,
        "price_monthly_usd": 0.00,
        "price_yearly_usd": 0.00,
    },
    {
        "name": "Plus",
        "plan_type": PlanType.PLUS,
        "max_credits_per_month": 1000,
        "price_monthly_usd": 29.00,
        "price_yearly_usd": 290.00,
    },
    {
        "name": "VIP",
        "plan_type": PlanType.VIP,
        "max_credits_per_month": 5000,
        "price_monthly_usd": 99.00,
        "price_yearly_usd": 990.00,
    },
    {
        "name": "MVP",
        "plan_type": PlanType.MVP,
        "max_credits_per_month": 10000,
        "price_monthly_usd": 299.00,
        "price_yearly_usd": 2790.00,
    },
]


class PlanSeed:

    def __init__(self, plan_repo: PlanRepository) -> None:
        self._plan_repo = plan_repo

    async def execute(self) -> list[Plan]:
        created = []
        for plan_data in SEED_PLANS:
            existing = await self._plan_repo.get_by_type(plan_data["plan_type"])
            if not existing:
                plan = Plan(**plan_data)
                plan = await self._plan_repo.create(plan)
                created.append(plan)
        return created