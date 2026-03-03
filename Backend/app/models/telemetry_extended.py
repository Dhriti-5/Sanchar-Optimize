"""
Extended Telemetry Models
Session management and enhanced telemetry tracking
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum


class Platform(str, Enum):
    """Platform types"""
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"


class Modality(str, Enum):
    """Content modality types"""
    VIDEO = "video"
    AUDIO = "audio"
    TEXT_SUMMARY = "text_summary"


class TransitionReason(str, Enum):
    """Reasons for modality transitions"""
    PREDICTED_DROP = "predicted_drop"
    ACTUAL_DROP = "actual_drop"
    BANDWIDTH_LOW = "bandwidth_low"
    USER_MANUAL = "user_manual"
    AUTO_RESTORE = "auto_restore"


class SessionCreate(BaseModel):
    """Request model for session creation"""
    session_id: Optional[str] = Field(None, description="Client-generated session ID")
    platform: Platform = Field(Platform.WEB, description="Platform type")


class SessionResponse(BaseModel):
    """Response model for session operations"""
    session_id: str
    status: str
    message: str


class ContentPosition(BaseModel):
    """Content position tracking"""
    content_id: str = Field(..., description="Content identifier (video ID, URL)")
    timestamp: float = Field(..., description="Current position in seconds")
    modality: Modality = Field(..., description="Current modality")
    semantic_context: Optional[str] = Field(None, description="Semantic description of current position")


class ModalityTransition(BaseModel):
    """Modality transition event"""
    content_id: str
    from_modality: Modality
    to_modality: Modality
    timestamp: float = Field(..., description="Content timestamp when transition occurred")
    reason: TransitionReason
    network_conditions: Dict[str, Any] = Field(..., description="Network metrics at transition")


class EnhancedTelemetryData(BaseModel):
    """Enhanced telemetry with session and location"""
    session_id: str
    signal_strength: float = Field(..., ge=0, le=100, description="Signal strength percentage")
    latency: float = Field(..., ge=0, description="Network latency in milliseconds")
    packet_loss: float = Field(0, ge=0, le=100, description="Packet loss percentage")
    bandwidth_mbps: float = Field(..., ge=0, description="Available bandwidth in Mbps")
    velocity_kmh: float = Field(0, ge=0, description="GPS velocity in km/h")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    network_type: str = Field("4g", description="Network type (2g, 3g, 4g, 5g)")
    effective_type: Optional[str] = Field(None, description="Effective network type from browser")


class TelemetryBatch(BaseModel):
    """Batch telemetry submission"""
    session_id: str
    telemetry_data: List[EnhancedTelemetryData]


class LocationStatistics(BaseModel):
    """Statistical summary for a location"""
    location_grid: str
    signal_strength: Dict[str, float]
    latency: Dict[str, float]
    bandwidth: Dict[str, float]
    sample_count: int
    time_range_hours: int


class ShadowZone(BaseModel):
    """Geographic shadow zone information"""
    location_grid: str
    avg_signal_strength: float
    sample_count: int
    risk_level: str  # "high", "medium", "low"
