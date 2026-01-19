"""Access Control Service - Interfaces with EnGarde backend for user subscription info"""

import httpx
import logging
import os
from typing import Optional
from app.models.access_control import UserAccessControl, SubscriptionTier, WalkerAgentType, TierLimits

logger = logging.getLogger(__name__)


class AccessControlService:
    """Service for retrieving user access control from EnGarde backend"""

    def __init__(self):
        self.engarde_api_url = os.getenv("ENGARDE_API_URL", "https://api.engarde.media")
        self.engarde_api_key = os.getenv("ENGARDE_API_KEY", "")
        self.timeout = 10.0  # seconds

    async def get_user_access_control(self, user_id: str) -> Optional[UserAccessControl]:
        """
        Fetch user's subscription tier and enabled walker agents from EnGarde backend.

        Args:
            user_id: UUID of the user

        Returns:
            UserAccessControl object or None if user not found
        """
        try:
            endpoint = f"{self.engarde_api_url}/api/users/{user_id}/access-control"

            headers = {
                "Authorization": f"Bearer {self.engarde_api_key}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers)

                if response.status_code == 404:
                    logger.warning(f"User {user_id} not found in EnGarde backend")
                    return None

                response.raise_for_status()
                data = response.json()

                logger.info(f"Retrieved access control for user {user_id}: {data}")

                # Parse response into UserAccessControl model
                return UserAccessControl(
                    user_id=data["user_id"],
                    subscription_tier=data["subscription_tier"],
                    enabled_walker_agents=data.get("enabled_walker_agents", []),
                    tier_limits=TierLimits(**data.get("tier_limits", self._get_default_tier_limits(data["subscription_tier"]))),
                    is_active=data.get("is_active", True),
                    tenant_id=data.get("tenant_id")
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error retrieving access control for user {user_id}: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error retrieving access control for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving access control for user {user_id}: {e}", exc_info=True)
            raise

    def _get_default_tier_limits(self, tier: str) -> dict:
        """
        Get default tier limits if not provided by EnGarde backend.

        This is a fallback - the EnGarde backend should provide these limits.
        """
        tier_limits_map = {
            SubscriptionTier.FREE: {
                "max_flows": 5,
                "max_walker_agents": 0,
                "max_campaigns": 1,
                "api_rate_limit": 100
            },
            SubscriptionTier.PRO: {
                "max_flows": 50,
                "max_walker_agents": 2,
                "max_campaigns": 10,
                "api_rate_limit": 1000
            },
            SubscriptionTier.ENTERPRISE: {
                "max_flows": 200,
                "max_walker_agents": 4,
                "max_campaigns": 100,
                "api_rate_limit": 10000
            },
            SubscriptionTier.AGENCY: {
                "max_flows": 1000,
                "max_walker_agents": 4,
                "max_campaigns": 1000,
                "api_rate_limit": 50000
            }
        }

        return tier_limits_map.get(tier, tier_limits_map[SubscriptionTier.FREE])

    async def get_tier_hierarchy(self) -> dict:
        """
        Get tier hierarchy for upgrade path calculations.

        Returns:
            Dictionary mapping tier to its numeric level
        """
        return {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.PRO: 1,
            SubscriptionTier.ENTERPRISE: 2,
            SubscriptionTier.AGENCY: 3
        }

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
            SubscriptionTier.PRO: 1,
            SubscriptionTier.ENTERPRISE: 2,
            SubscriptionTier.AGENCY: 3
        }

        user_level = tier_hierarchy.get(user_tier, 0)
        required_level = tier_hierarchy.get(required_tier, 0)

        return user_level >= required_level

    def has_walker_agent_enabled(
        self,
        enabled_agents: list,
        required_agent: Optional[WalkerAgentType]
    ) -> bool:
        """
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
