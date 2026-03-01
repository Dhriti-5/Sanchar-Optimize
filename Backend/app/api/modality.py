"""
Modality Decision API Endpoints
Handles modality transition decisions and panic signals
"""

from fastapi import APIRouter, HTTPException, status
import logging

from app.models.modality import (
    ModalityDecisionRequest,
    ModalityDecisionResponse,
    PanicSignalRequest,
    ModalityStatus
)
from app.services.modality_orchestrator import ModalityOrchestrator
from app.aws.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Modality Orchestrator (singleton)
_modality_orchestrator: ModalityOrchestrator | None = None


def get_modality_orchestrator() -> ModalityOrchestrator:
    """Get or create Modality Orchestrator instance"""
    global _modality_orchestrator
    
    if _modality_orchestrator is None:
        logger.info("Initializing Modality Orchestrator...")
        bedrock_client = BedrockClient()
        _modality_orchestrator = ModalityOrchestrator(bedrock_client=bedrock_client)
    
    return _modality_orchestrator


@router.post("/modality/decide", response_model=ModalityDecisionResponse)
async def decide_modality_transition(request: ModalityDecisionRequest):
    """
    Make AI-powered modality transition decision
    
    Args:
        request: Decision request with network and content context
        
    Returns:
        Decision response with target modality and reasoning
    """
    try:
        orchestrator = get_modality_orchestrator()
        decision = await orchestrator.decide_modality_transition(request)
        
        return decision
        
    except Exception as e:
        logger.error(f"Modality decision error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/modality/panic", response_model=ModalityDecisionResponse)
async def handle_panic_signal(request: PanicSignalRequest):
    """
    Handle emergency panic signal from extension
    
    When network drops suddenly, make immediate decision
    
    Args:
        request: Panic signal request
        
    Returns:
        Immediate modality decision
    """
    try:
        orchestrator = get_modality_orchestrator()
        decision = await orchestrator.handle_panic_signal(request)
        
        return decision
        
    except Exception as e:
        logger.error(f"Panic signal handling error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/modality/status/{session_id}", response_model=ModalityStatus)
async def get_modality_status(session_id: str):
    """
    Get current modality status for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        Current modality status
    """
    try:
        orchestrator = get_modality_orchestrator()
        status_data = orchestrator.get_session_status(session_id)
        
        if status_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        return status_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/modality/session/{session_id}")
async def clear_session_state(session_id: str):
    """
    Clear session state
    
    Args:
        session_id: Session identifier
        
    Returns:
        Success status
    """
    try:
        orchestrator = get_modality_orchestrator()
        orchestrator.clear_session(session_id)
        
        return {
            "status": "success",
            "message": "Session state cleared",
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Session clear error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/modality/health")
async def modality_health_check():
    """
    Check modality service health
    
    Returns:
        Health status including Bedrock connectivity
    """
    try:
        orchestrator = get_modality_orchestrator()
        
        # Test Bedrock connectivity (simple test)
        test_available = orchestrator.bedrock_client.client is not None
        
        return {
            "status": "healthy",
            "bedrock_available": test_available,
            "active_sessions": len(orchestrator.session_states)
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "degraded",
            "error": str(e)
        }
