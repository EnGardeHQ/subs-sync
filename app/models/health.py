"""Health check models"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response"""
    service: str = Field(description="Service name")
    status: str = Field(description="Service status")
    version: str = Field(description="Service version")
