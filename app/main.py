"""
EnGarde Subscription-Based Template Sync Service

Microservice for syncing Langflow templates with subscription tier and walker agent gating.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging
import os

from app.services.sync_engine import TemplateSyncEngine
from app.services.access_control import AccessControlService
from app.auth.verify import verify_service_token
from app.models.sync_request import SyncRequest, SyncResponse
from app.models.health import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EnGarde Subscription Sync Service",
    description="Template synchronization with subscription tier and walker agent gating",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to EnGarde domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - service info"""
    return {
        "service": "EnGarde Subscription Sync Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Railway"""
    return {
        "service": "subscription-sync",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.post("/sync/{user_id}", response_model=SyncResponse)
async def sync_user_templates(
    user_id: str,
    force_sync: bool = False,
    authorization: Optional[str] = Header(None)
):
    """
    Sync templates for a user based on their subscription tier and enabled walker agents.

    Args:
        user_id: UUID of the user to sync templates for
        force_sync: Force re-sync even if templates are up-to-date
        authorization: Bearer token for service-to-service auth

    Returns:
        SyncResponse with sync results
    """
    try:
        logger.info(f"Sync request received for user: {user_id}")

        # Verify service token
        if not verify_service_token(authorization):
            raise HTTPException(status_code=401, detail="Invalid or missing authorization token")

        # Get user's access control from EnGarde backend
        access_control_service = AccessControlService()
        user_access = await access_control_service.get_user_access_control(user_id)

        if not user_access:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found in EnGarde backend")

        logger.info(
            f"User access control retrieved: tier={user_access.subscription_tier}, "
            f"enabled_agents={user_access.enabled_walker_agents}"
        )

        # Perform template sync with tier and agent filtering
        sync_engine = TemplateSyncEngine()
        sync_result = await sync_engine.sync_user_templates(
            user_id=user_id,
            user_access=user_access,
            force_sync=force_sync
        )

        logger.info(f"Sync completed for user {user_id}: {sync_result}")

        return sync_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Template sync failed: {str(e)}")


@app.get("/sync/{user_id}/status")
async def get_sync_status(
    user_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get current sync status for a user - what templates they have access to.

    Args:
        user_id: UUID of the user
        authorization: Bearer token for service-to-service auth

    Returns:
        Current template access and sync status
    """
    try:
        # Verify service token
        if not verify_service_token(authorization):
            raise HTTPException(status_code=401, detail="Invalid or missing authorization token")

        # Get user's access control
        access_control_service = AccessControlService()
        user_access = await access_control_service.get_user_access_control(user_id)

        if not user_access:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        # Get sync status
        sync_engine = TemplateSyncEngine()
        status = await sync_engine.get_user_sync_status(user_id, user_access)

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync status for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@app.post("/sync/{user_id}/check-access/{template_id}")
async def check_template_access(
    user_id: str,
    template_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Check if a user has access to a specific template.

    Args:
        user_id: UUID of the user
        template_id: UUID of the template
        authorization: Bearer token for service-to-service auth

    Returns:
        Access status and reason if denied
    """
    try:
        # Verify service token
        if not verify_service_token(authorization):
            raise HTTPException(status_code=401, detail="Invalid or missing authorization token")

        # Get user's access control
        access_control_service = AccessControlService()
        user_access = await access_control_service.get_user_access_control(user_id)

        if not user_access:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        # Check template access
        sync_engine = TemplateSyncEngine()
        access_result = await sync_engine.check_template_access(
            template_id=template_id,
            user_access=user_access
        )

        return access_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check template access: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check access: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
