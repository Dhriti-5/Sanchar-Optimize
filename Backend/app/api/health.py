"""
Health Check Endpoints
Provides system health and readiness checks
"""

from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
import logging

from app.aws.bedrock_client import BedrockClient
from app.aws.dynamodb_client import dynamodb_client
from app.aws.timestream_client import timestream_client

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: float
    service: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response"""
    ready: bool
    checks: dict
    timestamp: float


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check endpoint
    Returns 200 if service is running
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().timestamp(),
        service="sanchar-optimize",
        version="2.0.0"
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness check endpoint
    Checks if service is ready to handle requests
    """
    bedrock_client = BedrockClient()
    checks = {
        "api": True,  # API is ready if we reach this point
        "bedrock": bedrock_client.client is not None,
        "dynamodb": dynamodb_client.available,
        "timestream": timestream_client.available,
    }
    
    all_ready = all(checks.values())
    
    return ReadinessResponse(
        ready=all_ready,
        checks=checks,
        timestamp=datetime.now().timestamp()
    )


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """
    Liveness check endpoint
    Returns 200 if service is alive (for K8s liveness probe)
    """
    return {"status": "alive"}
