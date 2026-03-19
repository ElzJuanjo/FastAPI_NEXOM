"""
Registry central de entidades.
Importa TODAS las entidades para que SQLAlchemy las registre en el mapper.
"""

from .base import Base
from .user import User, UserAuthProvider
from .plan import Plan
from .organization import Organization, Subscription, OrganizationMember
from .brand import Brand
from .product import Product
from .agent import AgentTask
from .flow import Flow, FlowStep
from .creative import Creative
from .landing_page import LandingPage, LandingPageSection
from .copy_asset import CopyAsset
from .conversion import ConversionAnalysis, OptimizationRecommendation
from .activity_log import ActivityLog
from .creative_batch import CreativeBatch