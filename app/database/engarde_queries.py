"""Database queries for EnGarde PostgreSQL database (subscription tiers and walker agents)"""

import logging
from typing import List, Dict, Optional
from app.database.connection import db
from app.models.access_control import SubscriptionTier, WalkerAgentType, TierLimits

logger = logging.getLogger(__name__)


class EnGardeQueries:
    """Database queries for EnGarde main application database"""

    @staticmethod
    async def get_user_subscription_data(user_id: str) -> Optional[Dict]:
        """
        Get user's subscription tier and enabled walker agents from EnGarde database.

        Expected EnGarde database schema:
        - users table: id, email, subscription_tier
        - user_walker_agents table: user_id, walker_agent_type, enabled

        Args:
            user_id: User UUID

        Returns:
            Dict with subscription_tier and enabled_walker_agents, or None if user not found
        """
        async with db.get_engarde_connection() as conn:
            # Get user's subscription tier
            user_row = await conn.fetchrow(
                """
                SELECT id, email, subscription_tier, is_active
                FROM users
                WHERE id = $1
                """,
                user_id
            )

            if not user_row:
                logger.warning(f"User {user_id} not found in EnGarde database")
                return None

            subscription_tier = user_row['subscription_tier'] or 'free'
            is_active = user_row.get('is_active', True)

            # Get enabled walker agents for this user
            agent_rows = await conn.fetch(
                """
                SELECT walker_agent_type
                FROM user_walker_agents
                WHERE user_id = $1 AND enabled = true
                """,
                user_id
            )

            enabled_walker_agents = [row['walker_agent_type'] for row in agent_rows]

            logger.info(
                f"Retrieved subscription data for user {user_id}: "
                f"tier={subscription_tier}, agents={enabled_walker_agents}"
            )

            return {
                'user_id': str(user_row['id']),
                'email': user_row['email'],
                'subscription_tier': subscription_tier,
                'enabled_walker_agents': enabled_walker_agents,
                'is_active': is_active
            }

    @staticmethod
    def get_tier_limits(tier: SubscriptionTier) -> TierLimits:
        """
        Get resource limits for a subscription tier.

        In a production system, these would likely be stored in the database.
        For now, we define them here.

        Args:
            tier: Subscription tier

        Returns:
            TierLimits object
        """
        tier_limits_map = {
            SubscriptionTier.FREE: TierLimits(
                max_flows=5,
                max_walker_agents=0,
                max_campaigns=1,
                api_rate_limit=100
            ),
            SubscriptionTier.PRO: TierLimits(
                max_flows=50,
                max_walker_agents=2,
                max_campaigns=10,
                api_rate_limit=1000
            ),
            SubscriptionTier.ENTERPRISE: TierLimits(
                max_flows=200,
                max_walker_agents=4,
                max_campaigns=100,
                api_rate_limit=10000
            ),
            SubscriptionTier.AGENCY: TierLimits(
                max_flows=1000,
                max_walker_agents=4,
                max_campaigns=1000,
                api_rate_limit=50000
            )
        }

        return tier_limits_map.get(tier, tier_limits_map[SubscriptionTier.FREE])

    @staticmethod
    async def get_user_tenant_id(user_id: str) -> Optional[str]:
        """
        Get user's tenant ID for multi-tenant support.

        Args:
            user_id: User UUID

        Returns:
            Tenant ID or None
        """
        async with db.get_engarde_connection() as conn:
            # Check if tenant_id column exists
            column_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'tenant_id'
                )
                """
            )

            if not column_exists:
                return None

            row = await conn.fetchrow(
                """
                SELECT tenant_id FROM users WHERE id = $1
                """,
                user_id
            )

            if row and row['tenant_id']:
                return str(row['tenant_id'])
            return None
