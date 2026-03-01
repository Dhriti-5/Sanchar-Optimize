"""
Telemetry API Endpoints
Handles network telemetry ingestion and signal drop predictions
"""

from fastapi import APIRouter, HTTPException, status
from typing import List
import logging

from app.models.telemetry import (
    NetworkTelemetry,
    TelemetryBatch,
    PredictionRequest,
    PredictionResponse
)
from app.services.network_sentry import NetworkSentryAgent
from app.ml.model_loader import ModelLoader

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Network Sentry Agent (singleton)
_network_sentry: NetworkSentryAgent | None = None


def get_network_sentry() -> NetworkSentryAgent:
    """Get or create Network Sentry Agent instance"""
    global _network_sentry
    
    if _network_sentry is None:
        logger.info(">>> Initializing Network Sentry Agent <<<")
        predictor = ModelLoader.load_lstm_predictor()
        
        if predictor.model is not None:
            logger.info(">>> Network Sentry initialized WITH LSTM MODEL <<<")
        else:
            logger.warning(">>> Network Sentry initialized with HEURISTIC FALLBACK <<<")
        
        _network_sentry = NetworkSentryAgent(predictor=predictor)
    
    return _network_sentry


@router.post("/telemetry", status_code=status.HTTP_201_CREATED)
async def submit_telemetry(telemetry: NetworkTelemetry):
    """
    Submit a single network telemetry data point
    
    Args:
        telemetry: Network telemetry data
        
    Returns:
        Success status
    """
    try:
        sentry = get_network_sentry()
        success = sentry.ingest_telemetry(telemetry)
        
        if success:
            return {
                "status": "success",
                "message": "Telemetry ingested successfully",
                "device_id": telemetry.device_id,
                "session_id": telemetry.session_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to ingest telemetry"
            )
    except Exception as e:
        logger.error(f"Telemetry submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/telemetry/batch", status_code=status.HTTP_201_CREATED)
async def submit_telemetry_batch(batch: TelemetryBatch):
    """
    Submit a batch of network telemetry data points
    
    Args:
        batch: Batch of telemetry data
        
    Returns:
        Batch ingestion result
    """
    try:
        sentry = get_network_sentry()
        success_count = sentry.ingest_telemetry_batch(batch.telemetry)
        
        return {
            "status": "success",
            "message": f"Batch ingested: {success_count}/{len(batch.telemetry)} successful",
            "device_id": batch.device_id,
            "session_id": batch.session_id,
            "total_points": len(batch.telemetry),
            "successful_points": success_count
        }
    except Exception as e:
        logger.error(f"Batch telemetry submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/telemetry/predict", response_model=PredictionResponse)
async def predict_signal_drop(request: PredictionRequest):
    """
    Get signal drop prediction based on recent telemetry
    
    Args:
        request: Prediction request with recent telemetry
        
    Returns:
        Prediction response with recommended action
    """
    try:
        sentry = get_network_sentry()
        
        # Run prediction
        prediction_response = sentry.predict_signal_drop(
            device_id=request.device_id,
            session_id=request.session_id,
            recent_telemetry=request.recent_telemetry
        )
        
        return prediction_response
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/telemetry/monitoring-frequency/{device_id}/{session_id}")
async def get_monitoring_frequency(device_id: str, session_id: str):
    """
    Get recommended monitoring frequency for a device/session
    
    Args:
        device_id: Device identifier
        session_id: Session identifier
        
    Returns:
        Recommended monitoring frequency
    """
    try:
        sentry = get_network_sentry()
        frequency_hz = sentry.get_monitoring_frequency(device_id, session_id)
        
        return {
            "device_id": device_id,
            "session_id": session_id,
            "frequency_hz": frequency_hz,
            "interval_ms": int(1000 / frequency_hz)
        }
        
    except Exception as e:
        logger.error(f"Frequency check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/telemetry/recent/{device_id}/{session_id}")
async def get_recent_telemetry(device_id: str, session_id: str, count: int = 30):
    """
    Get recent telemetry points for a device/session
    
    Args:
        device_id: Device identifier
        session_id: Session identifier
        count: Number of recent points to retrieve
        
    Returns:
        List of recent telemetry points
    """
    try:
        sentry = get_network_sentry()
        recent = sentry.get_recent_telemetry(device_id, session_id, count)
        
        return {
            "device_id": device_id,
            "session_id": session_id,
            "count": len(recent),
            "telemetry": recent
        }
        
    except Exception as e:
        logger.error(f"Recent telemetry fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/telemetry/session/{device_id}/{session_id}")
async def clear_session_telemetry(device_id: str, session_id: str):
    """
    Clear telemetry data for a session
    
    Args:
        device_id: Device identifier
        session_id: Session identifier
        
    Returns:
        Success status
    """
    try:
        sentry = get_network_sentry()
        sentry.clear_session_data(device_id, session_id)
        
        return {
            "status": "success",
            "message": "Session telemetry cleared",
            "device_id": device_id,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Session clear error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
