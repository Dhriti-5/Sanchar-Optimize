"""
Session Management API
Handles user session creation, tracking, and contextual memory
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
import uuid

from app.aws.dynamodb_client import dynamodb_client
from app.models.telemetry_extended import (
    SessionCreate, 
    SessionResponse, 
    ContentPosition, 
    ModalityTransition,
    ResumeSyncRequest,
    ResumeSyncResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/session", tags=["session"])


def calculate_resume_timestamp(
    source_position: Optional[float],
    fallback_timestamp: float,
    summary_read_seconds: float,
    content_duration_seconds: Optional[float] = None
) -> float:
    base_position = source_position if source_position is not None else fallback_timestamp
    mapped = max(0.0, base_position + max(0.0, summary_read_seconds))

    if content_duration_seconds is not None:
        mapped = min(mapped, max(0.0, content_duration_seconds))

    return mapped


@router.post("/create", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    user_agent: str = Header(..., alias="User-Agent")
):
    """
    Create a new user session
    
    SessionID should be generated client-side for offline resilience
    """
    try:
        session_id = session_data.session_id or str(uuid.uuid4())
        
        success = await dynamodb_client.create_session(
            session_id=session_id,
            user_agent=user_agent,
            platform=session_data.platform
        )
        
        if not success:
            if not dynamodb_client.available:
                raise HTTPException(
                    status_code=503, 
                    detail="DynamoDB service unavailable. Check AWS credentials and network connectivity."
                )
            else:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to create session in DynamoDB"
                )
        
        return SessionResponse(
            session_id=session_id,
            status="created",
            message="Session created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=dict)
async def get_session(session_id: str):
    """
    Retrieve session data
    Auto-creates session on first access if it doesn't exist (lazy initialization)
    """
    try:
        session = await dynamodb_client.get_session(session_id)
        
        if not session:
            # Session doesn't exist yet - create it on first access
            # This handles cases where initial creation failed (e.g., health check was failing)
            logger.info(f"Session {session_id} not found, auto-creating on first access...")
            
            success = await dynamodb_client.create_session(
                session_id=session_id,
                user_agent="browser",  # Default user agent
                platform="web"  # Default platform
            )
            
            if not success:
                raise HTTPException(
                    status_code=503,
                    detail="Could not create session. DynamoDB unavailable."
                )
            
            # Fetch the newly created session
            session = await dynamodb_client.get_session(session_id)
            
            if not session:
                raise HTTPException(
                    status_code=500,
                    detail="Session created but could not be retrieved"
                )
            
            logger.info(f"Session {session_id} auto-created successfully")
        
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/position")
async def update_position(
    session_id: str,
    position: ContentPosition
):
    """
    Update current content position (Contextual Memory)
    
    This is called frequently to maintain exact position tracking
    across modality transitions
    """
    try:
        success = await dynamodb_client.update_content_position(
            session_id=session_id,
            content_id=position.content_id,
            timestamp=position.timestamp,
            modality=position.modality,
            semantic_context=position.semantic_context
        )
        
        if not success and not dynamodb_client.available:
            # Graceful degradation
            return {
                "status": "local_only",
                "message": "Position updated locally only"
            }
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update position")
        
        return {
            "status": "success",
            "session_id": session_id,
            "content_id": position.content_id,
            "timestamp": position.timestamp
        }
        
    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/position/{content_id}")
async def get_position(session_id: str, content_id: str):
    """
    Get last known position in content
    
    Used for "Resume" functionality when returning to video
    """
    try:
        position = await dynamodb_client.get_content_position(session_id, content_id)
        
        if not position:
            return {
                "status": "not_found",
                "message": "No saved position found"
            }
        
        return {
            "status": "found",
            "position": position
        }
        
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/transition")
async def record_transition(
    session_id: str,
    transition: ModalityTransition
):
    """
    Record a modality transition event (Multi-Modal Handshake)
    
    This creates an audit trail of all modality changes for analytics
    and debugging
    """
    try:
        success = await dynamodb_client.record_modality_transition(
            session_id=session_id,
            content_id=transition.content_id,
            from_modality=transition.from_modality,
            to_modality=transition.to_modality,
            timestamp=transition.timestamp,
            reason=transition.reason,
            network_conditions=transition.network_conditions
        )
        
        if not success and not dynamodb_client.available:
            return {
                "status": "local_only",
                "message": "Transition recorded locally only"
            }
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to record transition")
        
        return {
            "status": "success",
            "message": "Transition recorded"
        }
        
    except Exception as e:
        logger.error(f"Error recording transition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/transitions")
async def get_transitions(session_id: str, limit: int = 50):
    """
    Get transition history for a session
    
    Returns the complete Multi-Modal Handshake history
    """
    try:
        transitions = await dynamodb_client.get_transition_history(session_id, limit)
        
        return {
            "session_id": session_id,
            "transition_count": len(transitions),
            "transitions": transitions
        }
        
    except Exception as e:
        logger.error(f"Error getting transitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/resume-map", response_model=ResumeSyncResponse)
async def map_resume_position(session_id: str, request: ResumeSyncRequest):
    """Map semantic summary progress back to a video timestamp."""
    try:
        source_position = None
        saved = await dynamodb_client.get_content_position(session_id, request.content_id)
        if saved and isinstance(saved, dict):
            source_position = saved.get("timestamp")

        mapped_timestamp = calculate_resume_timestamp(
            source_position=source_position,
            fallback_timestamp=request.fallback_timestamp,
            summary_read_seconds=request.summary_read_seconds,
            content_duration_seconds=request.content_duration_seconds
        )

        await dynamodb_client.update_content_position(
            session_id=session_id,
            content_id=request.content_id,
            timestamp=mapped_timestamp,
            modality="video",
            semantic_context=request.summary_anchor_text
        )

        return ResumeSyncResponse(
            status="success",
            mapped_timestamp=mapped_timestamp,
            source_position=source_position,
            applied_offset_seconds=max(0.0, request.summary_read_seconds),
            semantic_anchor=request.summary_anchor_text,
            message="Resume position mapped successfully"
        )
    except Exception as e:
        logger.error(f"Error mapping resume position: {e}")
        raise HTTPException(status_code=500, detail=str(e))
