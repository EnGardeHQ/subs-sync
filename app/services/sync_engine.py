"""Template Sync Engine - Core synchronization logic with subscription tier gating"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from app.models.access_control import UserAccessControl, TemplateMetadata, TemplateAccessResult, SubscriptionTier
from app.models.sync_request import SyncResponse, TemplateSyncResult, SyncStatusResponse
from app.database.queries import LangflowQueries
from app.services.access_control import AccessControlService

logger = logging.getLogger(__name__)


class TemplateSyncEngine:
    """
    Template synchronization engine with subscription tier and walker agent gating.

    Admin Folder Structure:
    - "Walker Agents" folder: Contains walker agent templates (subscription-gated)
    - "En Garde Flows" folder: Contains free-tier templates (everyone gets these)

    Non-Admin Folder Structure:
    - "En Garde" folder: Contains all accessible templates
      - Walker Agents (filtered by tier + enabled agents)
      - En Garde Flows (all users get these - FREE)
    """

    ADMIN_WALKER_AGENTS_FOLDER = "Walker Agents"
    ADMIN_ENGARDE_FLOWS_FOLDER = "En Garde Flows"
    USER_ENGARDE_FOLDER = "En Garde"

    def __init__(self):
        self.access_control = AccessControlService()
        self.queries = LangflowQueries()

    async def sync_user_templates(
        self,
        user_id: str,
        user_access: UserAccessControl,
        force_sync: bool = False
    ) -> SyncResponse:
        """
        Sync templates to user's folder based on subscription tier and enabled walker agents.

        Args:
            user_id: User UUID
            user_access: User's access control (tier, enabled agents, etc.)
            force_sync: Force re-sync even if up-to-date

        Returns:
            SyncResponse with sync results
        """
        try:
            logger.info(
                f"Starting template sync for user {user_id}: "
                f"tier={user_access.subscription_tier}, agents={user_access.enabled_walker_agents}"
            )

            # Step 0: Verify user exists in Langflow database
            langflow_user = await self.queries.get_user(user_id)
            if not langflow_user:
                error_msg = f"User {user_id} not found in Langflow database. User must log in via SSO first."
                logger.warning(error_msg)
                return SyncResponse(
                    user_id=user_id,
                    sync_timestamp=datetime.utcnow(),
                    status="skipped",
                    new_flows_added=[],
                    flows_updated=[],
                    flows_up_to_date=0,
                    flows_denied=[],
                    folders_created=[],
                    total_templates_available=0,
                    total_templates_accessible=0,
                    total_templates_synced=0,
                    subscription_tier=user_access.subscription_tier,
                    enabled_walker_agents=user_access.enabled_walker_agents,
                    message=error_msg
                )

            # Step 1: Ensure user has "En Garde" folder
            engarde_folder_id = await self.queries.get_or_create_folder(
                user_id=user_id,
                folder_name=self.USER_ENGARDE_FOLDER
            )

            folders_created = [self.USER_ENGARDE_FOLDER] if engarde_folder_id else []

            # Step 2: Get all admin templates
            admin_templates = await self.queries.get_admin_templates()
            logger.info(f"Found {len(admin_templates)} admin templates")

            # Step 3: Categorize templates by access level
            accessible_templates = []
            denied_templates = []

            for template in admin_templates:
                metadata = template['metadata']
                access_check = self._check_template_access(template, user_access)

                if access_check['has_access']:
                    accessible_templates.append(template)
                else:
                    denied_templates.append({
                        'template': template,
                        'reason': access_check['reason']
                    })

            logger.info(
                f"Access check complete: {len(accessible_templates)} accessible, "
                f"{len(denied_templates)} denied"
            )

            # Step 4: Sync accessible templates
            sync_results = await self._sync_templates_to_folder(
                user_id=user_id,
                folder_id=engarde_folder_id,
                templates=accessible_templates,
                force_sync=force_sync
            )

            # Step 5: Build response
            response = SyncResponse(
                user_id=user_id,
                sync_timestamp=datetime.utcnow(),
                status="success",
                new_flows_added=sync_results['new_flows'],
                flows_updated=sync_results['updated_flows'],
                flows_up_to_date=sync_results['up_to_date_count'],
                flows_denied=[
                    TemplateSyncResult(
                        flow_id="",
                        template_id=d['template']['id'],
                        name=d['template']['name'],
                        template_version=d['template']['metadata']['version'],
                        folder=d['template']['folder_name'] or "Unknown",
                        action="denied",
                        denial_reason=d['reason']
                    )
                    for d in denied_templates
                ],
                total_templates_available=len(admin_templates),
                total_templates_accessible=len(accessible_templates),
                total_templates_synced=len(sync_results['new_flows']) + sync_results['up_to_date_count'],
                subscription_tier=user_access.subscription_tier,
                enabled_walker_agents=user_access.enabled_walker_agents,
                folders_created=folders_created
            )

            logger.info(f"Sync completed successfully for user {user_id}")
            return response

        except Exception as e:
            logger.error(f"Sync failed for user {user_id}: {e}", exc_info=True)
            raise

    def _check_template_access(
        self,
        template: Dict,
        user_access: UserAccessControl
    ) -> Dict:
        """
        Check if user has access to a template based on tier and walker agent.

        Logic:
        - En Garde Flows (category=engarde_flows): Everyone gets (FREE tier)
        - Walker Agents (category=walker_agents): Requires:
          1. Subscription tier >= required_tier
          2. Specific walker agent must be enabled

        Args:
            template: Template dict with metadata
            user_access: User's access control

        Returns:
            Dict with 'has_access' (bool) and 'reason' (str if denied)
        """
        metadata = template['metadata']
        required_tier = SubscriptionTier(metadata['required_tier'])
        walker_agent_type = metadata.get('walker_agent_type')
        category = metadata.get('category', 'engarde_flows')

        # En Garde Flows are FREE - everyone gets them
        if category == 'engarde_flows':
            return {'has_access': True, 'reason': None}

        # Walker Agents require tier check AND agent enablement check
        if category == 'walker_agents':
            # Check tier
            if not self.access_control.can_access_tier(user_access.subscription_tier, required_tier):
                return {
                    'has_access': False,
                    'reason': f"Requires {required_tier.value} tier or higher (current: {user_access.subscription_tier.value})"
                }

            # Check walker agent access (tier must allow walker agent type AND agent must be enabled)
            if not self.access_control.has_walker_agent_access(
                user_access.subscription_tier,
                user_access.enabled_walker_agents,
                walker_agent_type
            ):
                tier_allowed = self.access_control.get_tier_allowed_walker_agents(user_access.subscription_tier)
                return {
                    'has_access': False,
                    'reason': (
                        f"Walker agent '{walker_agent_type.value if walker_agent_type else 'unknown'}' "
                        f"not accessible. Tier {user_access.subscription_tier.value} allows: "
                        f"{[a.value for a in tier_allowed]}"
                    )
                }

            return {'has_access': True, 'reason': None}

        # Unknown category - deny by default
        return {
            'has_access': False,
            'reason': f"Unknown template category: {category}"
        }

    async def _sync_templates_to_folder(
        self,
        user_id: str,
        folder_id: str,
        templates: List[Dict],
        force_sync: bool
    ) -> Dict:
        """
        Sync accessible templates to user's folder.

        Args:
            user_id: User UUID
            folder_id: Target folder UUID
            templates: List of accessible templates
            force_sync: Force re-sync even if flow exists

        Returns:
            Dict with sync results
        """
        new_flows = []
        updated_flows = []
        up_to_date_count = 0

        for template in templates:
            # Check if user already has this flow
            flow_exists = await self.queries.flow_exists_for_user(user_id, template['name'])

            if flow_exists and not force_sync:
                up_to_date_count += 1
                logger.debug(f"Flow '{template['name']}' already exists for user {user_id}")
                continue

            # Copy template to user's folder
            try:
                new_flow_id = await self.queries.copy_template_to_user(
                    user_id=user_id,
                    template=template,
                    folder_id=folder_id
                )

                result = TemplateSyncResult(
                    flow_id=new_flow_id,
                    template_id=template['id'],
                    name=template['name'],
                    template_version=template['metadata']['version'],
                    folder=self.USER_ENGARDE_FOLDER,
                    action="created" if not flow_exists else "updated",
                    denial_reason=None
                )

                if flow_exists:
                    updated_flows.append(result)
                else:
                    new_flows.append(result)

            except Exception as e:
                logger.error(f"Failed to copy template '{template['name']}' to user {user_id}: {e}")
                # Continue with other templates even if one fails

        return {
            'new_flows': new_flows,
            'updated_flows': updated_flows,
            'up_to_date_count': up_to_date_count
        }

    async def get_user_sync_status(
        self,
        user_id: str,
        user_access: UserAccessControl
    ) -> SyncStatusResponse:
        """
        Get current sync status for a user.

        Args:
            user_id: User UUID
            user_access: User's access control

        Returns:
            SyncStatusResponse with current status
        """
        # Get all admin templates
        admin_templates = await self.queries.get_admin_templates()

        # Get user's current flows
        user_flows = await self.queries.get_user_flows(user_id)

        # Calculate accessible templates
        accessible_count = 0
        denied_count = 0
        upgrade_opportunities = []

        for template in admin_templates:
            access_check = self._check_template_access(template, user_access)

            if access_check['has_access']:
                accessible_count += 1
            else:
                denied_count += 1

                # Track upgrade opportunities (templates available in higher tiers)
                if "Requires" in access_check['reason']:
                    upgrade_opportunities.append({
                        'template_name': template['name'],
                        'required_tier': template['metadata']['required_tier'],
                        'walker_agent_type': template['metadata'].get('walker_agent_type'),
                        'features': template['metadata'].get('features', [])
                    })

        return SyncStatusResponse(
            user_id=user_id,
            subscription_tier=user_access.subscription_tier,
            enabled_walker_agents=user_access.enabled_walker_agents,
            last_sync_at=None,  # TODO: Track last sync timestamp
            total_flows=len(user_flows),
            template_flows_count=len(user_flows),  # TODO: Distinguish template vs custom flows
            custom_flows_count=0,  # TODO: Distinguish template vs custom flows
            accessible_templates=accessible_count,
            pending_updates=0,  # TODO: Track version updates
            denied_templates=denied_count,
            upgrade_opportunities=upgrade_opportunities
        )

    async def check_template_access(
        self,
        template_id: str,
        user_access: UserAccessControl
    ) -> TemplateAccessResult:
        """
        Check if user has access to a specific template.

        Args:
            template_id: Template UUID
            user_access: User's access control

        Returns:
            TemplateAccessResult
        """
        # Get all admin templates (TODO: optimize to fetch single template)
        admin_templates = await self.queries.get_admin_templates()

        template = next((t for t in admin_templates if t['id'] == template_id), None)

        if not template:
            return TemplateAccessResult(
                has_access=False,
                template_id=template_id,
                template_name="Unknown",
                reason="Template not found",
                required_tier=None,
                required_walker_agent=None,
                upgrade_url=None
            )

        access_check = self._check_template_access(template, user_access)
        metadata = template['metadata']

        return TemplateAccessResult(
            has_access=access_check['has_access'],
            template_id=template_id,
            template_name=template['name'],
            reason=access_check['reason'],
            required_tier=SubscriptionTier(metadata['required_tier']) if not access_check['has_access'] else None,
            required_walker_agent=metadata.get('walker_agent_type'),
            upgrade_url="https://engarde.media/pricing" if not access_check['has_access'] else None
        )
