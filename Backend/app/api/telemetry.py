"""
Telemetry API Endpoints
Handles network telemetry ingestion and signal drop predictions
"""

from fastapi import APIRouter, HTTPException, status
from typing import List
from datetime import datetime
import logging

from app.models.telemetry import (
    NetworkTelemetry,
    TelemetryBatch,
    PredictionRequest,
    PredictionResponse
)
from app.models.telemetry_extended import EnhancedTelemetryData
from app.services.network_sentry import NetworkSentryAgent
from app.ml.model_loader import ModelLoader
from app.aws.timestream_client import timestream_client

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


@router.post("/telemetry/enhanced", status_code=status.HTTP_201_CREATED)
async def submit_enhanced_telemetry(telemetry: EnhancedTelemetryData):
    """
    Submit enhanced telemetry with persistent storage to Timestream
    
    This endpoint provides scalable historical telemetry tracking
    for shadow zone detection and pattern analysis
    
    Args:
        telemetry: Enhanced telemetry data with location
        
    Returns:
        Success status
    """
    try:
        # Store in Timestream for historical analysis
        timestream_success = await timestream_client.write_telemetry(
            session_id=telemetry.session_id,
            signal_strength=telemetry.signal_strength,
            latency=telemetry.latency,
            packet_loss=telemetry.packet_loss,
            bandwidth_mbps=telemetry.bandwidth_mbps,
            velocity_kmh=telemetry.velocity_kmh,
            latitude=telemetry.latitude,
            longitude=telemetry.longitude,
            network_type=telemetry.network_type
        )
        
        # Also ingest into Network Sentry for real-time prediction
        # Convert EnhancedTelemetryData to NetworkTelemetry with proper field mapping
        timestamp_seconds = telemetry.timestamp / 1000.0 if telemetry.timestamp else datetime.now().timestamp()
        
        basic_telemetry = NetworkTelemetry(
            device_id=telemetry.session_id,  # Use session_id as device_id
            session_id=telemetry.session_id,
            timestamp=timestamp_seconds,  # Convert milliseconds to seconds
            signal_strength=telemetry.signal_strength / 100.0,  # Convert 0-100 to 0-1
            latency_ms=int(telemetry.latency),  # Map latency to latency_ms
            packet_loss_percent=telemetry.packet_loss,  # Map packet_loss to packet_loss_percent
            bandwidth_kbps=telemetry.bandwidth_mbps * 1000,  # Convert Mbps to Kbps
            gps_velocity_kmh=telemetry.velocity_kmh  # Map velocity_kmh to gps_velocity_kmh
        )
        
        sentry = get_network_sentry()
        sentry_success = sentry.ingest_telemetry(basic_telemetry)
        
        status_msg = "success"
        if not timestream_success and not sentry_success:
            status_msg = "failed"
        elif not timestream_success:
            status_msg = "partial_success_no_persistence"
        elif not sentry_success:
            status_msg = "partial_success_no_prediction"
        
        return {
            "status": status_msg,
            "message": "Enhanced telemetry processed",
            "session_id": telemetry.session_id,
            "timestream_stored": timestream_success,
            "sentry_ingested": sentry_success
        }
        
    except Exception as e:
        logger.error(f"Enhanced telemetry submission error: {e}")
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


@router.get("/telemetry/location/history")
async def get_location_history(
    latitude: float,
    longitude: float,
    time_range_hours: int = 24
):
    """
    Get historical network patterns for a geographic location
    
    This powers predictive intelligence by analyzing past network behavior
    in specific areas (e.g., known dead zones on train routes)
    
    Args:
        latitude: GPS latitude
        longitude: GPS longitude
        time_range_hours: Hours of history to retrieve (default 24)
        
    Returns:
        Historical telemetry data
    """
    try:
        history = await timestream_client.query_historical_patterns(
            latitude=latitude,
            longitude=longitude,
            time_range_hours=time_range_hours
        )
        
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "time_range_hours": time_range_hours,
            "record_count": len(history),
            "history": history
        }
        
    except Exception as e:
        logger.error(f"Location history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/telemetry/location/statistics")
async def get_location_statistics(
    latitude: float,
    longitude: float,
    time_range_hours: int = 168  # 7 days
):
    """
    Get statistical summary of network conditions for a location
    
    Used for "Speculative Agent" pre-caching decisions
    
    Args:
        latitude: GPS latitude
        longitude: GPS longitude
        time_range_hours: Analysis time window (default 7 days)
        
    Returns:
        Statistical metrics
    """
    try:
        stats = await timestream_client.get_location_statistics(
            latitude=latitude,
            longitude=longitude,
            time_range_hours=time_range_hours
        )
        
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "time_range_hours": time_range_hours,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Location statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/telemetry/shadow-zones")
async def get_shadow_zones(min_samples: int = 50):
    """
    Identify geographic "shadow zones" with consistently poor network
    
    Powers the pre-caching strategy by identifying high-risk areas
    where content should be pre-downloaded
    
    Args:
        min_samples: Minimum samples required to classify a zone
        
    Returns:
        List of shadow zones with risk classification
    """
    try:
        zones = await timestream_client.identify_shadow_zones(min_samples=min_samples)
        
        # Classify risk level
        for zone in zones:
            signal = zone['avg_signal_strength']
            if signal < 30:
                zone['risk_level'] = 'high'
            elif signal < 50:
                zone['risk_level'] = 'medium'
            else:
                zone['risk_level'] = 'low'
        
        return {
            "zone_count": len(zones),
            "min_samples": min_samples,
            "shadow_zones": zones
        }
        
    except Exception as e:
        logger.error(f"Shadow zones error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
