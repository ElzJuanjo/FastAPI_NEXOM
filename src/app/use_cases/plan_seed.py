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
        "max_tasks_per_month": 50,
        "max_agents": 3,
        "has_api_access": False,
        "price_monthly_usd": 0.00,
        "price_yearly_usd": 0.00,
    },
    {
        "name": "Pro",
        "plan_type": PlanType.PRO,
        "max_tasks_per_month": 500,
        "max_agents": 10,
        "has_api_access": True,
        "price_monthly_usd": 49.00,
        "price_yearly_usd": 468.00,
    },
    {
        "name": "Enterprise",
        "plan_type": PlanType.ENTERPRISE,
        "max_tasks_per_month": 99999,
        "max_agents": 99,
        "has_api_access": True,
        "price_monthly_usd": 199.00,
        "price_yearly_usd": 1908.00,
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