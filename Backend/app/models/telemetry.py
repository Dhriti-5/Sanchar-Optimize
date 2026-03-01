"""
Telemetry Data Models
Represents network telemetry data collected from client devices
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class NetworkTelemetry(BaseModel):
    """Network telemetry data point"""
    
    device_id: str = Field(..., description="Unique device identifier (anonymized)")
    session_id: str = Field(..., description="Current user session ID")
    timestamp: float = Field(..., description="Unix timestamp of measurement")
    
    # Network metrics
    signal_strength: float = Field(..., ge=0.0, le=1.0, description="Signal strength (0-1)")
    latency_ms: int = Field(..., ge=0, description="Network latency in milliseconds")
    packet_loss_percent: float = Field(..., ge=0.0, le=100.0, description="Packet loss percentage")
    bandwidth_kbps: float = Field(..., ge=0, description="Available bandwidth in Kbps")
    
    # GPS data
    gps_velocity_kmh: float = Field(default=0.0, ge=0.0, le=500.0, description="GPS velocity in km/h")
    location_hash: Optional[str] = Field(None, description="Anonymized location hash")
    
    # Context
    content_id: Optional[str] = Field(None, description="Current content being played")
    content_position: Optional[float] = Field(None, description="Current playback position (seconds)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "device_abc123",
                "session_id": "session_xyz789",
                "timestamp": 1709251200.0,
                "signal_strength": 0.75,
                "latency_ms": 150,
                "packet_loss_percent": 2.5,
                "bandwidth_kbps": 1200.0,
                "gps_velocity_kmh": 45.0,
                "location_hash": "h3_891f1d4",
                "content_id": "video_edu_123",
                "content_position": 120.5
            }
        }


class TelemetryBatch(BaseModel):
    """Batch of telemetry data points"""
    
    device_id: str
    session_id: str
    telemetry: list[NetworkTelemetry] = Field(..., min_length=1, max_length=100)
    
    @validator('telemetry')
    def validate_device_consistency(cls, v, values):
        """Ensure all telemetry points belong to same device"""
        device_id = values.get('device_id')
        for point in v:
            if point.device_id != device_id:
                raise ValueError(f"Telemetry point device_id mismatch: {point.device_id} != {device_id}")
        return v


class SignalDropPrediction(BaseModel):
    """Predicted signal drop event"""
    
    model_config = {
        "protected_namespaces": (),  # Allow "model_" prefix
        "json_schema_extra": {
            "example": {
                "prediction_id": "pred_abc123",
                "device_id": "device_abc123",
                "session_id": "session_xyz789",
                "timestamp": 1709251200.0,
                "confidence": 0.85,
                "predicted_time_seconds": 3.5,
                "predicted_bandwidth_kbps": 450.0,
                "prediction_horizon_seconds": 5,
                "model_version": "lstm_v1",
                "predictor_type": "lstm",
                "features_used": ["signal_strength", "latency_ms", "gps_velocity_kmh"]
            }
        }
    }
    
    prediction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    session_id: str
    timestamp: float
    
    # Prediction details
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence (0-1)")
    predicted_time_seconds: float = Field(..., ge=0.0, le=10.0, description="Time until signal drop")
    predicted_bandwidth_kbps: float = Field(..., ge=0, description="Predicted minimum bandwidth")
    prediction_horizon_seconds: int = Field(default=5, description="Prediction time window")
    
    # Model metadata
    model_version: str = Field(default="lstm_v1", description="Model version used")
    predictor_type: str = Field(default="heuristic", description="Predictor type used (lstm/heuristic)") 
    features_used: list[str] = Field(default_factory=list, description="Features used for prediction")


class PredictionRequest(BaseModel):
    """Request for signal drop prediction"""
    
    device_id: str
    session_id: str
    recent_telemetry: list[NetworkTelemetry] = Field(..., min_length=5, max_length=30, 
                                                       description="Recent telemetry history (5-30 points)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "device_abc123",
                "session_id": "session_xyz789",
                "recent_telemetry": []  # Would contain actual telemetry points
            }
        }


class PredictionResponse(BaseModel):
    """Response with signal drop prediction"""
    
    prediction: Optional[SignalDropPrediction]
    should_prepare_transition: bool = Field(..., description="Whether to prepare for modality transition")
    recommended_action: str = Field(..., description="Recommended action")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prediction": {
                    "prediction_id": "pred_abc123",
                    "confidence": 0.85,
                    "predicted_time_seconds": 3.5
                },
                "should_prepare_transition": True,
                "recommended_action": "PREPARE_AUDIO_FALLBACK"
            }
        }
