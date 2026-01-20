"""Access Control Service - Direct database access for user subscription info"""

import logging
from typing import Optional
from app.models.access_control import UserAccessControl, SubscriptionTier, WalkerAgentType, TierLimits
from app.database.engarde_queries import EnGardeQueries

logger = logging.getLogger(__name__)


class AccessControlService:
    """Service for retrieving user access control from EnGarde database"""

    def __init__(self):
        self.engarde_queries = EnGardeQueries()

    async def get_user_access_control(self, user_id: str) -> Optional[UserAccessControl]:
        """
        Fetch user's subscription tier and enabled walker agents from EnGarde database.

        Args:
            user_id: UUID of the user

        Returns:
            UserAccessControl object or None if user not found
        """
        try:
            # Get user subscription data from EnGarde database
            user_data = await self.engarde_queries.get_user_subscription_data(user_id)

            if not user_data:
                logger.warning(f"User {user_id} not found in EnGarde database")
                return None

            # Parse subscription tier
            tier = SubscriptionTier(user_data['subscription_tier'])

            # Parse enabled walker agents
            enabled_agents = []
            for agent_str in user_data['enabled_walker_agents']:
                try:
                    enabled_agents.append(WalkerAgentType(agent_str))
                except ValueError:
                    logger.warning(f"Unknown walker agent type: {agent_str}")

            # Get tier limits
            tier_limits = self.engarde_queries.get_tier_limits(tier)

            # Get tenant ID
            tenant_id = await self.engarde_queries.get_user_tenant_id(user_id)

            logger.info(
                f"Retrieved access control for user {user_id}: "
                f"tier={tier.value}, agents={[a.value for a in enabled_agents]}"
            )

            return UserAccessControl(
                user_id=user_id,
                subscription_tier=tier,
                enabled_walker_agents=enabled_agents,
                tier_limits=tier_limits,
                is_active=user_data.get('is_active', True),
                tenant_id=tenant_id
            )

        except Exception as e:
            logger.error(f"Failed to retrieve access control for user {user_id}: {e}", exc_info=True)
            raise

    def can_access_tier(self, user_tier: SubscriptionTier, required_tier: SubscriptionTier) -> bool:
        """
        Check if user's tier can access a resource requiring a specific tier.

        Args:
            user_tier: User's subscription tier
            required_tier: Required tier for the resource

        Returns:
            True if user can access, False otherwise
        """
        tier_hierarchy = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.STARTER: 0,  # Same level as FREE
            SubscriptionTier.PRO: 1,
            SubscriptionTier.PROFESSIONAL: 1,  # Same level as PRO
            SubscriptionTier.BUSINESS: 2,  # Higher than PRO, lower than ENTERPRISE
            SubscriptionTier.ENTERPRISE: 3,
            SubscriptionTier.AGENCY: 3  # Same level as ENTERPRISE
        }

        user_level = tier_hierarchy.get(user_tier, 0)
        required_level = tier_hierarchy.get(required_tier, 0)

        return user_level >= required_level

    def get_tier_allowed_walker_agents(self, subscription_tier: SubscriptionTier) -> list:
        """
        Get list of walker agents allowed by subscription tier.

        Tier-based walker agent access:
        - STARTER/FREE: SEO + Content (Capilytic only)
        - PROFESSIONAL/PRO: Paid Ads (Sankore only)
        - BUSINESS: All 4 walker agents
        - ENTERPRISE/AGENCY: All 4 walker agents + custom settings

        Args:
            subscription_tier: User's subscription tier

        Returns:
            List of WalkerAgentType that tier allows access to
        """
        tier_walker_access = {
            SubscriptionTier.FREE: [WalkerAgentType.SEO, WalkerAgentType.CONTENT],
            SubscriptionTier.STARTER: [WalkerAgentType.SEO, WalkerAgentType.CONTENT],
            SubscriptionTier.PRO: [WalkerAgentType.PAID_ADS],
            SubscriptionTier.PROFESSIONAL: [WalkerAgentType.PAID_ADS],
            SubscriptionTier.BUSINESS: [
                WalkerAgentType.SEO,
                WalkerAgentType.CONTENT,
                WalkerAgentType.PAID_ADS,
                WalkerAgentType.AUDIENCE_INTELLIGENCE
            ],
            SubscriptionTier.ENTERPRISE: [
                WalkerAgentType.SEO,
                WalkerAgentType.CONTENT,
                WalkerAgentType.PAID_ADS,
                WalkerAgentType.AUDIENCE_INTELLIGENCE
            ],
            SubscriptionTier.AGENCY: [
                WalkerAgentType.SEO,
                WalkerAgentType.CONTENT,
                WalkerAgentType.PAID_ADS,
                WalkerAgentType.AUDIENCE_INTELLIGENCE
            ]
        }

        return tier_walker_access.get(subscription_tier, [])

    def has_walker_agent_access(
        self,
        subscription_tier: SubscriptionTier,
        enabled_agents: list,
        required_agent: Optional[WalkerAgentType]
    ) -> bool:
        """
        Check if user has access to a walker agent based on:
        1. Subscription tier (tier must allow this walker agent type)
        2. Enabled status (walker agent must be enabled for the user)

        Args:
            subscription_tier: User's subscription tier
            enabled_agents: List of walker agents enabled for the user
            required_agent: Required walker agent (None if not a walker agent template)

        Returns:
            True if user has access, False otherwise
        """
        if required_agent is None:
            return True  # Not a walker agent template, no agent requirement

        # Check if tier allows this walker agent
        tier_allowed = self.get_tier_allowed_walker_agents(subscription_tier)
        if required_agent not in tier_allowed:
            logger.warning(
                f"Walker agent {required_agent.value} not allowed by tier {subscription_tier.value}. "
                f"Tier allows: {[a.value for a in tier_allowed]}"
            )
            return False

        # Check if walker agent is enabled for user
        if required_agent not in enabled_agents:
            logger.warning(
                f"Walker agent {required_agent.value} not enabled for user. "
                f"Enabled agents: {[a.value for a in enabled_agents]}"
            )
            return False

        return True

    def has_walker_agent_enabled(
        self,
        enabled_agents: list,
        required_agent: Optional[WalkerAgentType]
    ) -> bool:
        """
        DEPRECATED: Use has_walker_agent_access() instead which includes tier checking.

        Check if a required walker agent is enabled for the user.

        Args:
            enabled_agents: List of enabled walker agents for the user
            required_agent: Required walker agent (None if not a walker agent template)

        Returns:
            True if agent is enabled or not required, False otherwise
        """
        if required_agent is None:
            return True  # Not a walker agent template, no agent requirement

        return required_agent in enabled_agents
