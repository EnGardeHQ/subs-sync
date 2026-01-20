"""Database queries for Langflow PostgreSQL database"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4
import json

from app.database.connection import db

logger = logging.getLogger(__name__)


class LangflowQueries:
    """Database queries for Langflow flow, folder, and user tables"""

    # ============================================================================
    # FOLDER QUERIES
    # ============================================================================

    @staticmethod
    async def get_or_create_folder(
        user_id: str,
        folder_name: str,
        parent_id: Optional[str] = None
    ) -> str:
        """
        Get or create a folder for a user.

        Args:
            user_id: User UUID
            folder_name: Name of the folder
            parent_id: Parent folder UUID (None for root folder)

        Returns:
            Folder UUID
        """
        async with db.get_langflow_connection() as conn:
            # Check if folder exists
            if parent_id:
                folder = await conn.fetchrow(
                    """
                    SELECT id FROM folder
                    WHERE user_id = $1 AND name = $2 AND parent_id = $3
                    """,
                    user_id, folder_name, parent_id
                )
            else:
                folder = await conn.fetchrow(
                    """
                    SELECT id FROM folder
                    WHERE user_id = $1 AND name = $2 AND parent_id IS NULL
                    """,
                    user_id, folder_name
                )

            if folder:
                return str(folder['id'])

            # Create folder
            folder_id = str(uuid4())

            await conn.execute(
                """
                INSERT INTO folder (id, name, user_id, parent_id)
                VALUES ($1, $2, $3, $4)
                """,
                folder_id, folder_name, user_id, parent_id
            )

            logger.info(f"Created folder '{folder_name}' for user {user_id}")
            return folder_id

    # ============================================================================
    # ADMIN TEMPLATE QUERIES
    # ============================================================================

    @staticmethod
    async def get_admin_templates() -> List[Dict]:
        """
        Get all admin template flows from the designated template-admin account.

        Template flows are managed by superusers and system admins who all share
        the template-admin@engarde.com account in Langflow.

        Returns:
            List of admin templates with metadata
        """
        async with db.get_langflow_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    f.id, f.name, f.data, f.description, f.updated_at,
                    fol.name as folder_name,
                    u.username as admin_username
                FROM flow f
                JOIN "user" u ON f.user_id = u.id
                LEFT JOIN folder fol ON f.folder_id = fol.id
                WHERE u.username = 'template-admin@engarde.com'
                ORDER BY fol.name, f.name
                """
            )

            templates = []
            for row in rows:
                # Parse template metadata from description (JSON format)
                metadata = LangflowQueries._parse_template_metadata(row['description'])

                templates.append({
                    'id': str(row['id']),
                    'name': row['name'],
                    'data': row['data'],
                    'description': row['description'],
                    'folder_name': row['folder_name'],
                    'admin_username': row['admin_username'],
                    'updated_at': row['updated_at'],
                    'metadata': metadata
                })

            logger.info(f"Retrieved {len(templates)} admin templates")
            return templates

    @staticmethod
    def _parse_template_metadata(description: Optional[str]) -> Dict:
        """
        Parse template metadata from description field.

        Expected format in description:
        {
            "user_description": "This flow does X, Y, Z",
            "template_metadata": {
                "required_tier": "pro",
                "walker_agent_type": "seo",
                "category": "walker_agents",
                "features": ["keyword_research"],
                "version": "1.0.0"
            }
        }

        Args:
            description: Flow description (may contain JSON metadata)

        Returns:
            Template metadata dict with defaults
        """
        default_metadata = {
            'required_tier': 'free',
            'walker_agent_type': None,
            'category': 'engarde_flows',
            'features': [],
            'version': '1.0.0'
        }

        if not description:
            return default_metadata

        try:
            desc_obj = json.loads(description)
            if isinstance(desc_obj, dict) and 'template_metadata' in desc_obj:
                metadata = desc_obj['template_metadata']
                # Merge with defaults
                return {**default_metadata, **metadata}
        except (json.JSONDecodeError, TypeError):
            # Description is plain text, not JSON
            pass

        return default_metadata

    # ============================================================================
    # USER FLOW QUERIES
    # ============================================================================

    @staticmethod
    async def get_user_flows(user_id: str) -> List[Dict]:
        """
        Get all flows for a user (both custom and synced from templates).

        Args:
            user_id: User UUID

        Returns:
            List of user's flows
        """
        async with db.get_langflow_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, folder_id, data, description, created_at, updated_at
                FROM flow
                WHERE user_id = $1
                ORDER BY name
                """,
                user_id
            )

            return [dict(row) for row in rows]

    @staticmethod
    async def copy_template_to_user(
        user_id: str,
        template: Dict,
        folder_id: str
    ) -> str:
        """
        Copy an admin template flow to a user's folder.

        Args:
            user_id: User UUID
            template: Admin template dict
            folder_id: Target folder UUID

        Returns:
            New flow UUID
        """
        async with db.get_langflow_connection() as conn:
            new_flow_id = str(uuid4())

            # Extract clean user description (remove template_metadata)
            clean_description = LangflowQueries._get_clean_description(template['description'])

            # Use CURRENT_TIMESTAMP to let PostgreSQL handle timezone
            await conn.execute(
                """
                INSERT INTO flow (
                    id, user_id, name, description, data, folder_id,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                """,
                new_flow_id,
                user_id,
                template['name'],
                clean_description,
                json.dumps(template['data']) if isinstance(template['data'], dict) else template['data'],
                folder_id
            )

            logger.info(f"Copied template '{template['name']}' to user {user_id} (flow_id: {new_flow_id})")
            return new_flow_id

    @staticmethod
    def _get_clean_description(description: Optional[str]) -> str:
        """
        Extract user-facing description, removing template_metadata.

        Args:
            description: Original description (may contain template_metadata)

        Returns:
            Clean user-facing description
        """
        if not description:
            return ""

        try:
            desc_obj = json.loads(description)
            if isinstance(desc_obj, dict) and 'user_description' in desc_obj:
                return desc_obj['user_description']
        except (json.JSONDecodeError, TypeError):
            # Plain text description
            return description

        return description

    @staticmethod
    async def flow_exists_for_user(user_id: str, flow_name: str) -> bool:
        """
        Check if a flow with given name already exists for user.

        Args:
            user_id: User UUID
            flow_name: Flow name to check

        Returns:
            True if flow exists, False otherwise
        """
        async with db.get_langflow_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM flow
                WHERE user_id = $1 AND name = $2
                """,
                user_id, flow_name
            )

            return row is not None

    # ============================================================================
    # USER QUERIES
    # ============================================================================

    @staticmethod
    async def get_user(user_id: str) -> Optional[Dict]:
        """
        Get user information from Langflow database by looking up via email.

        Since Langflow assigns its own UUIDs on user creation via SSO,
        we need to first get the user's email from EnGarde DB,
        then lookup the user in Langflow by username (which is the email).

        Args:
            user_id: EnGarde User UUID

        Returns:
            User dict or None if not found
        """
        # First, get user email from EnGarde database
        from app.database.engarde_queries import EnGardeQueries
        engarde_queries = EnGardeQueries()
        user_data = await engarde_queries.get_user_subscription_data(user_id)

        if not user_data or not user_data.get('email'):
            logger.warning(f"User {user_id} not found in EnGarde database")
            return None

        user_email = user_data['email']
        logger.info(f"Looking up Langflow user by email: {user_email} (EnGarde UUID: {user_id})")

        # Now lookup user in Langflow by username (email)
        async with db.get_langflow_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, username, is_superuser, is_active, last_login_at
                FROM "user"
                WHERE username = $1
                """,
                user_email
            )

            if row:
                logger.info(f"Found Langflow user: {row['username']} (Langflow UUID: {row['id']})")
                return dict(row)

            logger.warning(f"User {user_email} not found in Langflow database")
            return None
