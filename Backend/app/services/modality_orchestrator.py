"""
Modality Orchestrator Service
AI-powered decision engine for content modality transitions
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.models.modality import (
    Modality,
    TransitionTiming,
    ModalityDecisionRequest,
    ModalityDecisionResponse,
    PanicSignalRequest,
    ModalityStatus
)
from app.aws.bedrock_client import BedrockClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class ModalityOrchestrator:
    """
    Modality Orchestrator - AI Decision Engine
    
    Responsibilities:
    - Receive signal drop event notifications
    - Query Amazon Bedrock for optimal modality transition
    - Evaluate bandwidth, content importance, user context
    - Make autonomous modality transition decisions
    - Coordinate with content delivery and transformation services
    """
    
    def __init__(self, bedrock_client: Optional[BedrockClient] = None):
        """
        Initialize Modality Orchestrator
        
        Args:
            bedrock_client: Bedrock client instance (optional)
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        
        # In-memory session state (in production, use DynamoDB)
        self.session_states: Dict[str, ModalityStatus] = {}
        
        logger.info("Modality Orchestrator initialized")
    
    async def decide_modality_transition(
        self,
        request: ModalityDecisionRequest
    ) -> ModalityDecisionResponse:
        """
        Make AI-powered modality transition decision
        
        Args:
            request: Decision request with context
            
        Returns:
            Decision response with target modality and reasoning
        """
        try:
            start_time = datetime.now()
            
            logger.info(f"Making modality decision for session {request.session_id}: "
                       f"bandwidth={request.available_bandwidth_kbps:.0f} Kbps, "
                       f"current={request.current_modality}")
            
            # Prepare context for Bedrock
            context = {
                "available_bandwidth_kbps": request.available_bandwidth_kbps,
                "prediction_confidence": request.prediction_confidence,
                "time_to_signal_drop": request.time_to_signal_drop,
                "content_description": request.content_description,
                "content_position": request.content_position,
                "key_concepts": request.key_concepts,
                "visual_dependency_score": request.visual_dependency_score,
                "current_modality": request.current_modality.value,
                "transition_history": request.transition_history
            }
            
            # Get decision from Bedrock
            decision_data = await self.bedrock_client.get_modality_decision(context)
            
            # Parse decision
            target_modality = Modality(decision_data.get("target_modality", "VIDEO"))
            transition_timing = TransitionTiming(decision_data.get("transition_timing", "IMMEDIATE"))
            
            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            response = ModalityDecisionResponse(
                target_modality=target_modality,
                transition_timing=transition_timing,
                reasoning=decision_data.get("reasoning", "AI decision reasoning"),
                fallback_strategy=decision_data.get("fallback_strategy"),
                decision_confidence=decision_data.get("decision_confidence", 0.8),
                model_used=decision_data.get("model_used", "bedrock-claude-3.5-sonnet"),
                processing_time_ms=decision_data.get("processing_time_ms", processing_time_ms)
            )
            
            # Update session state
            self._update_session_state(
                session_id=request.session_id,
                device_id=request.device_id,
                content_id=request.content_id,
                from_modality=request.current_modality,
                to_modality=target_modality,
                content_position=request.content_position,
                success=True
            )
            
            logger.info(f"Decision made: {target_modality.value} with {response.decision_confidence:.2f} confidence")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to make modality decision: {e}")
            
            # Return safe fallback decision
            return self._get_safe_fallback_decision(request)
    
    async def handle_panic_signal(
        self,
        request: PanicSignalRequest
    ) -> ModalityDecisionResponse:
        """
        Handle emergency panic signal from extension
        
        When network drops suddenly, make immediate decision
        
        Args:
            request: Panic signal request
            
        Returns:
            Immediate modality decision
        """
        logger.warning(f"PANIC SIGNAL received for session {request.session_id}: "
                      f"bandwidth={request.current_bandwidth_kbps:.0f} Kbps, "
                      f"buffering={request.is_buffering}, "
                      f"buffer_level={request.buffer_level_seconds:.1f}s")
        
        # Fast rule-based decision for panic situations
        # No time to wait for AI inference
        
        bandwidth = request.current_bandwidth_kbps
        buffer_level = request.buffer_level_seconds
        
        if bandwidth < settings.AUDIO_MIN_BANDWIDTH or buffer_level < 1.0:
            # Critical: Go to text immediately
            target_modality = Modality.TEXT_SUMMARY
            timing = TransitionTiming.IMMEDIATE
            reasoning = "Critical network failure. Immediate transition to text summary to prevent complete interruption."
            confidence = 0.95
        elif bandwidth < settings.VIDEO_MIN_BANDWIDTH:
            # Moderate: Go to audio immediately
            target_modality = Modality.AUDIO
            timing = TransitionTiming.IMMEDIATE
            reasoning = "Severe bandwidth degradation. Immediate transition to audio to maintain content flow."
            confidence = 0.90
        else:
            # Minor: Stay in current modality but prepare
            target_modality = request.current_modality
            timing = TransitionTiming.WAIT_2S
            reasoning = "Bandwidth still acceptable. Monitoring situation before transition."
            confidence = 0.80
        
        response = ModalityDecisionResponse(
            target_modality=target_modality,
            transition_timing=timing,
            reasoning=reasoning,
            fallback_strategy="If fails, escalate to next lower modality",
            decision_confidence=confidence,
            model_used="rule-based-panic-handler",
            processing_time_ms=10  # Near-instant
        )
        
        # Update session state
        self._update_session_state(
            session_id=request.session_id,
            device_id=request.device_id,
            content_id=request.content_id,
            from_modality=request.current_modality,
            to_modality=target_modality,
            content_position=request.content_position,
            success=True
        )
        
        return response
    
    def get_session_status(self, session_id: str) -> Optional[ModalityStatus]:
        """
        Get current modality status for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            ModalityStatus if session exists, None otherwise
        """
        return self.session_states.get(session_id)
    
    def _update_session_state(
        self,
        session_id: str,
        device_id: str,
        content_id: str,
        from_modality: Modality,
        to_modality: Modality,
        content_position: float,
        success: bool
    ):
        """Update session state after transition decision"""
        
        if session_id not in self.session_states:
            # Initialize new session state
            self.session_states[session_id] = ModalityStatus(
                session_id=session_id,
                device_id=device_id,
                content_id=content_id,
                current_modality=to_modality,
                content_position=content_position,
                last_transition_timestamp=datetime.now().timestamp(),
                transition_count=0,
                transition_history=[],
                total_buffering_events=0,
                successful_transitions=0,
                failed_transitions=0
            )
        
        # Update status
        status = self.session_states[session_id]
        
        if from_modality != to_modality:
            # Record transition
            status.transition_count += 1
            status.transition_history.append({
                "from": from_modality.value,
                "to": to_modality.value,
                "timestamp": datetime.now().timestamp(),
                "position": content_position,
                "success": success
            })
            
            # Keep only recent transitions
            if len(status.transition_history) > 10:
                status.transition_history = status.transition_history[-10:]
            
            if success:
                status.successful_transitions += 1
            else:
                status.failed_transitions += 1
        
        status.current_modality = to_modality
        status.content_position = content_position
        status.last_transition_timestamp = datetime.now().timestamp()
        
        # In production: Persist to DynamoDB
        # await self.dynamodb_client.update_session(status)
    
    def _get_safe_fallback_decision(
        self,
        request: ModalityDecisionRequest
    ) -> ModalityDecisionResponse:
        """
        Get safe fallback decision when AI fails
        
        Args:
            request: Original request
            
        Returns:
            Safe fallback decision
        """
        bandwidth = request.available_bandwidth_kbps
        
        # Conservative rule-based decision
        if bandwidth >= settings.VIDEO_MIN_BANDWIDTH:
            target_modality = Modality.VIDEO
            reasoning = "Sufficient bandwidth. Maintaining video. [Fallback decision]"
        elif bandwidth >= settings.AUDIO_MIN_BANDWIDTH:
            target_modality = Modality.AUDIO
            reasoning = "Moderate bandwidth. Transitioning to audio. [Fallback decision]"
        else:
            target_modality = Modality.TEXT_SUMMARY
            reasoning = "Low bandwidth. Transitioning to text summary. [Fallback decision]"
        
        return ModalityDecisionResponse(
            target_modality=target_modality,
            transition_timing=TransitionTiming.IMMEDIATE,
            reasoning=reasoning,
            fallback_strategy="Continue best-effort delivery",
            decision_confidence=0.6,
            model_used="rule-based-fallback",
            processing_time_ms=5
        )
    
    def clear_session(self, session_id: str):
        """
        Clear session state
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.session_states:
            del self.session_states[session_id]
            logger.info(f"Cleared session state for {session_id}")
