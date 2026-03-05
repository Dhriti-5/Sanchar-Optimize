"""
Lambda Handler for Network Sentry Agent
Predicts network signal drops based on telemetry and GPS data
"""

import json
import logging
import os
from typing import Any, Dict

from app.services.network_sentry import NetworkSentryAgent
from app.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Network Sentry prediction.
    
    Expected event structure:
    {
        "device_id": "string",
        "telemetry": {
            "signal_strength": float (0-100),
            "bandwidth_kbps": float,
            "latency_ms": float,
            "packet_loss_percent": float,
            "gps_velocity_kmh": float,
            "timestamp": string (ISO 8601)
        }
    }
    
    Returns:
    {
        "prediction": {
            "signal_drop_probability": float (0-1),
            "time_to_drop_seconds": int,
            "confidence": float (0-1)
        },
        "should_prepare_transition": bool,
        "recommended_modality": "VIDEO|AUDIO|TEXT_SUMMARY"
    }
    """
    try:
        # Extract telemetry from event
        device_id = event.get("device_id")
        telemetry = event.get("telemetry")
        
        if not device_id or not telemetry:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing device_id or telemetry"})
            }
        
        # Create Network Sentry Agent
        sentry = NetworkSentryAgent()
        
        # Run prediction
        signal_strength = telemetry.get("signal_strength", 100)
        gps_velocity = telemetry.get("gps_velocity_kmh", 0)
        bandwidth = telemetry.get("bandwidth_kbps", 1000)
        latency = telemetry.get("latency_ms", 50)
        packet_loss = telemetry.get("packet_loss_percent", 0)
        
        # Simple LSTM-inspired prediction logic (production would use actual model)
        # Factors: high velocity + low signal + high latency = signal drop likely
        velocity_factor = min(gps_velocity / 100, 1.0)  # Normalized to [0,1]
        signal_factor = (100 - signal_strength) / 100  # Lower signal = higher risk
        latency_factor = min(latency / 200, 1.0)  # Normalized to [0,1]
        condition_factor = 1.0 if packet_loss > 5 else 0.5
        
        # Combined probability (weights based on empirical data)
        drop_probability = (
            velocity_factor * 0.3 +
            signal_factor * 0.4 +
            latency_factor * 0.2 +
            condition_factor * 0.1
        )
        
        # Confidence based on signal consistency (mock for now)
        confidence = min(drop_probability + 0.1, 1.0)
        
        # Estimate time to drop (based on velocity and signal trend)
        time_to_drop = max(5 - int(velocity_factor * 3), 1)
        
        # Determine if we should prepare transition
        should_prepare = (
            drop_probability > 0.6 and 
            confidence > 0.75 and
            gps_velocity > 40  # High-speed movement
        )
        
        # Recommend modality based on bandwidth
        if bandwidth > 1000:
            recommended_modality = "VIDEO"
        elif bandwidth > 500:
            recommended_modality = "AUDIO"
        else:
            recommended_modality = "TEXT_SUMMARY"
        
        logger.info(
            f"Signal prediction for {device_id}: "
            f"probability={drop_probability:.2f}, "
            f"confidence={confidence:.2f}, "
            f"time_to_drop={time_to_drop}s"
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "prediction": {
                    "signal_drop_probability": round(drop_probability, 3),
                    "time_to_drop_seconds": time_to_drop,
                    "confidence": round(confidence, 3)
                },
                "should_prepare_transition": should_prepare,
                "recommended_modality": recommended_modality,
                "bandwidth_kbps": bandwidth
            })
        }
        
    except Exception as e:
        logger.error(f"Error in Network Sentry handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
