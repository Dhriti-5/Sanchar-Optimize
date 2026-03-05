"""
Lambda Handler for Modality Orchestrator
Makes AI-powered decisions about content modality transitions
"""

import json
import logging
import os
from typing import Any, Dict

from app.services.modality_orchestrator import ModalityOrchestrator
from app.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Modality Orchestration decisions.
    
    Expected event structure:
    {
        "device_id": "string",
        "session_id": "string",
        "signal_drop_event": {
            "signal_drop_probability": float,
            "time_to_drop_seconds": int,
            "confidence": float
        },
        "current_context": {
            "bandwidth_kbps": float,
            "content_id": "string",
            "content_position": float,
            "content_title": "string",
            "transcript_snippet": "string (optional)"
        }
    }
    
    Returns:
    {
        "decision": {
            "target_modality": "VIDEO|AUDIO|TEXT_SUMMARY",
            "transition_latency_ms": int,
            "should_generate_summary": bool,
            "reasoning": "string"
        },
        "timestamp": "string (ISO 8601)"
    }
    """
    try:
        device_id = event.get("device_id")
        session_id = event.get("session_id")
        signal_drop = event.get("signal_drop_event", {})
        context = event.get("current_context", {})
        
        if not device_id or not session_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing device_id or session_id"})
            }
        
        # Create Modality Orchestrator
        orchestrator = ModalityOrchestrator()
        
        # Extract context
        bandwidth = context.get("bandwidth_kbps", 1000)
        content_id = context.get("content_id", "")
        signal_prob = signal_drop.get("signal_drop_probability", 0)
        confidence = signal_drop.get("confidence", 0)
        
        # Make modality decision based on bandwidth and risk
        if signal_prob < 0.5:
            # Low risk: maintain current modality
            target_modality = "VIDEO"
            reasoning = "Signal drop risk low; maintaining video"
        elif bandwidth > 1000:
            # Good bandwidth: keep video
            target_modality = "VIDEO"
            reasoning = "Adequate bandwidth for video despite signal risk"
        elif bandwidth > 500:
            # Medium bandwidth: use audio
            target_modality = "AUDIO"
            reasoning = "Signal drop predicted; transitioning to audio to preserve bandwidth"
        else:
            # Low bandwidth: use text summary
            target_modality = "TEXT_SUMMARY"
            reasoning = "Low bandwidth and signal instability; switching to AI-generated summary"
        
        should_generate_summary = target_modality == "TEXT_SUMMARY"
        
        logger.info(
            f"Modality decision for {device_id}: "
            f"target={target_modality}, bandwidth={bandwidth}kbps, "
            f"drop_prob={signal_prob:.2f}"
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "decision": {
                    "target_modality": target_modality,
                    "transition_latency_ms": 800,  # Target <2s total
                    "should_generate_summary": should_generate_summary,
                    "reasoning": reasoning
                },
                "device_id": device_id,
                "session_id": session_id,
                "content_id": content_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error in Modality Orchestrator handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
