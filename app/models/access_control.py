"""Access control models for subscription tiers and walker agent gating"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class SubscriptionTier(str, Enum):
    """
    Subscription tier levels with walker agent access control.

    Tier hierarchy (lowest to highest):
    FREE/STARTER → PROFESSIONAL → BUSINESS → ENTERPRISE

    Walker agent access by tier:
    - STARTER: Capilytic SEO + Content only
    - PROFESSIONAL: Sankore Paid Ads only
    - BUSINESS: All 4 walker agents
    - ENTERPRISE: All 4 walker agents + custom settings
    """
    FREE = "free"  # Legacy - maps to STARTER
    STARTER = "starter"  # Capilytic SEO + Content
    PRO = "pro"  # Legacy - maps to PROFESSIONAL
    PROFESSIONAL = "professional"  # Sankore Paid Ads only
    BUSINESS = "business"  # All 4 walker agents
    ENTERPRISE = "enterprise"  # All 4 + custom settings
    AGENCY = "agency"  # Legacy - maps to ENTERPRISE


class WalkerAgentType(str, Enum):
    """Types of walker agents"""
    SEO = "seo"
    CONTENT = "content"
    PAID_ADS = "paid_ads"
    AUDIENCE_INTELLIGENCE = "audience_intelligence"


class TierLimits(BaseModel):
    """Resource limits for a subscription tier"""
    max_flows: int = Field(description="Maximum number of flows user can create")
    max_walker_agents: int = Field(description="Maximum number of walker agents that can be enabled")
    max_campaigns: Optional[int] = Field(None, description="Maximum active campaigns")
    api_rate_limit: Optional[int] = Field(None, description="API requests per hour")


class UserAccessControl(BaseModel):
    """User's access control information from EnGarde backend"""
    user_id: str = Field(description="UUID of the user")
    subscription_tier: SubscriptionTier = Field(description="User's subscription tier")
    enabled_walker_agents: List[WalkerAgentType] = Field(
        default_factory=list,
        description="List of walker agents enabled for this user"
    )
    tier_limits: TierLimits = Field(description="Resource limits for user's tier")
    is_active: bool = Field(default=True, description="Whether subscription is active")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for multi-tenant support")

    class Config:
        use_enum_values = True


class TemplateMetadata(BaseModel):
    """Metadata for an admin template"""
    required_tier: SubscriptionTier = Field(description="Minimum tier required to access this template")
    walker_agent_type: Optional[WalkerAgentType] = Field(
        None,
        description="Walker agent type if this is a walker agent template"
    )
    category: str = Field(description="Template category (walker_agents, engarde_flows)")
    features: List[str] = Field(
        default_factory=list,
        description="List of features this template provides"
    )
    description: Optional[str] = Field(None, description="Template description")
    version: str = Field(default="1.0.0", description="Template version")

    class Config:
        use_enum_values = True


class TemplateAccessResult(BaseModel):
    """Result of checking if a user has access to a template"""
    has_access: bool = Field(description="Whether user has access to the template")
    template_id: str = Field(description="UUID of the template")
    template_name: str = Field(description="Name of the template")
    reason: Optional[str] = Field(None, description="Reason for denial if has_access=False")
    required_tier: Optional[SubscriptionTier] = Field(None, description="Required tier if denied due to tier")
    required_walker_agent: Optional[WalkerAgentType] = Field(
        None,
        description="Required walker agent if denied due to agent not enabled"
    )
    upgrade_url: Optional[str] = Field(None, description="URL to upgrade subscription if applicable")

    class Config:
        use_enum_values = True
