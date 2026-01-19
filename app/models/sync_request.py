"""Models for sync requests and responses"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class SyncRequest(BaseModel):
    """Request to sync templates for a user"""
    user_id: str = Field(description="UUID of the user to sync")
    force_sync: bool = Field(default=False, description="Force re-sync even if up-to-date")


class TemplateSyncResult(BaseModel):
    """Result of syncing a single template"""
    flow_id: str = Field(description="UUID of the synced flow")
    template_id: str = Field(description="UUID of the source admin template")
    name: str = Field(description="Flow name")
    template_version: str = Field(description="Template version")
    folder: str = Field(description="Folder where flow was placed")
    action: str = Field(description="Action taken: created, updated, skipped, denied")
    denial_reason: Optional[str] = Field(None, description="Reason if action=denied")


class SyncResponse(BaseModel):
    """Response from template sync operation"""
    user_id: str = Field(description="UUID of the user")
    sync_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When sync occurred")
    status: str = Field(description="Overall sync status: success, partial, failed, skipped")
    message: Optional[str] = Field(None, description="Optional message explaining the sync result")

    # Sync results
    new_flows_added: List[TemplateSyncResult] = Field(
        default_factory=list,
        description="Templates that were newly added"
    )
    flows_updated: List[TemplateSyncResult] = Field(
        default_factory=list,
        description="Templates that were updated to new versions"
    )
    flows_up_to_date: int = Field(default=0, description="Number of templates already up-to-date")
    flows_denied: List[TemplateSyncResult] = Field(
        default_factory=list,
        description="Templates that were denied due to tier/agent restrictions"
    )

    # Statistics
    total_templates_available: int = Field(description="Total admin templates in system")
    total_templates_accessible: int = Field(description="Templates user has access to")
    total_templates_synced: int = Field(description="Templates successfully synced")

    # User access summary
    subscription_tier: str = Field(description="User's subscription tier")
    enabled_walker_agents: List[str] = Field(description="User's enabled walker agents")

    # Folder structure
    folders_created: List[str] = Field(
        default_factory=list,
        description="Folders that were created during sync"
    )


class SyncStatusResponse(BaseModel):
    """Current sync status for a user"""
    user_id: str = Field(description="UUID of the user")
    subscription_tier: str = Field(description="User's subscription tier")
    enabled_walker_agents: List[str] = Field(description="Enabled walker agents")

    last_sync_at: Optional[datetime] = Field(None, description="When last sync occurred")
    total_flows: int = Field(description="Total flows user currently has")
    template_flows_count: int = Field(description="Number of flows synced from templates")
    custom_flows_count: int = Field(description="Number of user's custom flows")

    accessible_templates: int = Field(description="Templates user currently has access to")
    pending_updates: int = Field(description="Templates with updates available")
    denied_templates: int = Field(description="Templates user doesn't have access to")

    upgrade_opportunities: List[Dict] = Field(
        default_factory=list,
        description="Templates available in higher tiers"
    )
