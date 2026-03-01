"""
Modality Decision Models
Represents modality transition decisions and states
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class Modality(str, Enum):
    """Content modality types"""
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    TEXT_SUMMARY = "TEXT_SUMMARY"


class TransitionTiming(str, Enum):
    """When to execute modality transition"""
    IMMEDIATE = "IMMEDIATE"
    WAIT_2S = "WAIT_2S"
    WAIT_5S = "WAIT_5S"


class ModalityDecisionRequest(BaseModel):
    """Request for modality decision from Bedrock"""
    
    device_id: str
    session_id: str
    content_id: str
    content_position: float = Field(..., description="Current playback position (seconds)")
    
    # Network context
    available_bandwidth_kbps: float
    predicted_signal_drop: bool
    prediction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    time_to_signal_drop: Optional[float] = Field(None, description="Seconds until predicted drop")
    
    # Content context
    content_description: Optional[str] = Field(None, description="Brief content description")
    key_concepts: Optional[list[str]] = Field(default_factory=list, description="Key concepts in current segment")
    visual_dependency_score: float = Field(default=0.5, ge=0.0, le=1.0, description="How visual the content is")
    
    # User context
    current_modality: Modality = Field(default=Modality.VIDEO)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    transition_history: list[str] = Field(default_factory=list, description="Recent transition history")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "device_abc123",
                "session_id": "session_xyz789",
                "content_id": "video_edu_123",
                "content_position": 120.5,
                "available_bandwidth_kbps": 800.0,
                "predicted_signal_drop": True,
                "prediction_confidence": 0.85,
                "time_to_signal_drop": 3.5,
                "content_description": "Introduction to calculus derivatives",
                "key_concepts": ["derivative", "rate of change", "slope"],
                "visual_dependency_score": 0.7,
                "current_modality": "VIDEO",
                "user_preferences": {},
                "transition_history": []
            }
        }


class ModalityDecisionResponse(BaseModel):
    """Response with modality decision from AI"""
    
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    
    # Decision
    target_modality: Modality
    transition_timing: TransitionTiming
    reasoning: str = Field(..., description="AI reasoning for the decision")
    fallback_strategy: Optional[str] = Field(None, description="Fallback if primary fails")
    
    # Confidence
    decision_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    
    # Metadata
    model_used: str = Field(default="bedrock-claude-3.5-sonnet")
    processing_time_ms: Optional[int] = Field(None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec_abc123",
                "timestamp": 1709251200.0,
                "target_modality": "AUDIO",
                "transition_timing": "WAIT_2S",
                "reasoning": "Bandwidth dropping to 800 Kbps. Content can be understood in audio format. Wait 2s to complete current sentence.",
                "fallback_strategy": "If audio fails, transition to TEXT_SUMMARY",
                "decision_confidence": 0.88,
                "model_used": "bedrock-claude-3.5-sonnet",
                "processing_time_ms": 450
            }
        }


class PanicSignalRequest(BaseModel):
    """Emergency panic signal from extension when network drops suddenly"""
    
    device_id: str
    session_id: str
    content_id: str
    content_position: float
    current_modality: Modality
    
    # Emergency context
    current_bandwidth_kbps: float
    is_buffering: bool = Field(default=False)
    buffer_level_seconds: float = Field(default=0.0, description="Remaining buffer in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "device_abc123",
                "session_id": "session_xyz789",
                "content_id": "video_edu_123",
                "content_position": 125.0,
                "current_modality": "VIDEO",
                "current_bandwidth_kbps": 200.0,
                "is_buffering": True,
                "buffer_level_seconds": 2.5
            }
        }


class ModalityStatus(BaseModel):
    """Current modality status for a session"""
    
    session_id: str
    device_id: str
    content_id: str
    
    # Current state
    current_modality: Modality
    content_position: float
    last_transition_timestamp: Optional[float] = None
    
    # Transition history
    transition_count: int = Field(default=0)
    transition_history: list[Dict[str, Any]] = Field(default_factory=list)
    
    # Performance metrics
    total_buffering_events: int = Field(default=0)
    successful_transitions: int = Field(default=0)
    failed_transitions: int = Field(default=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_xyz789",
                "device_id": "device_abc123",
                "content_id": "video_edu_123",
                "current_modality": "AUDIO",
                "content_position": 130.5,
                "last_transition_timestamp": 1709251200.0,
                "transition_count": 2,
                "transition_history": [
                    {"from": "VIDEO", "to": "AUDIO", "timestamp": 1709251200.0}
                ],
                "total_buffering_events": 0,
                "successful_transitions": 2,
                "failed_transitions": 0
            }
        }
