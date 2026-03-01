"""
Amazon Bedrock Client
Handles interactions with Amazon Bedrock for AI-powered decisions
"""

import json
import logging
from typing import Dict, Any, Optional
import time

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception

from app.core.config import settings

logger = logging.getLogger(__name__)


class BedrockClient:
    """
    Client for Amazon Bedrock API
    Handles invocations of Claude 3.5 Sonnet for modality decisions
    """
    
    def __init__(self):
        """Initialize Bedrock client"""
        if boto3 is None:
            logger.warning("boto3 not installed. Bedrock client will use mock responses.")
            self.client = None
        else:
            try:
                self.client = boto3.client(
                    'bedrock-runtime',
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
                )
                logger.info(f"Bedrock client initialized for region {settings.AWS_REGION}")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock client: {e}")
                self.client = None
        
        self.model_id = settings.BEDROCK_MODEL_ID
        self.max_tokens = settings.BEDROCK_MAX_TOKENS
        self.temperature = settings.BEDROCK_TEMPERATURE
    
    async def invoke_model(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Invoke Bedrock model with a prompt
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Model response as dictionary
        """
        if self.client is None:
            logger.warning("Bedrock client not available. Using mock response.")
            return self._get_mock_response(prompt)
        
        try:
            start_time = time.time()
            
            # Prepare request body for Claude 3.5
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature or self.temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            if system_prompt:
                request_body["system"] = system_prompt
            
            # Invoke model
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Bedrock invocation successful: {processing_time_ms}ms")
            
            return {
                "success": True,
                "content": response_body['content'][0]['text'],
                "model": self.model_id,
                "processing_time_ms": processing_time_ms,
                "stop_reason": response_body.get('stop_reason', 'end_turn')
            }
            
        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": True
            }
        except Exception as e:
            logger.error(f"Unexpected error invoking Bedrock: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": True
            }
    
    async def get_modality_decision(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get modality transition decision from Bedrock
        
        Args:
            context: Decision context (bandwidth, content, user data, etc.)
            
        Returns:
            Decision response
        """
        # Build prompt from context
        prompt = self._build_modality_decision_prompt(context)
        
        system_prompt = """You are an intelligent content delivery agent. Your role is to decide the optimal content modality (VIDEO, AUDIO, or TEXT_SUMMARY) based on network conditions and content importance.

Consider:
1. Educational value - preserve critical learning content
2. Network constraints - adapt to  bandwidth limitations
3. User experience - minimize disruption
4. Content type - some content requires visual elements

Respond with valid JSON only, no additional text."""
        
        # Invoke Bedrock
        response = await self.invoke_model(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent decisions
        )
        
        if response.get("success"):
            # Parse JSON response
            try:
                decision = json.loads(response["content"])
                decision["processing_time_ms"] = response.get("processing_time_ms")
                return decision
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Bedrock JSON response: {e}")
                return self._get_fallback_decision(context)
        else:
            logger.warning("Bedrock invocation failed. Using fallback decision.")
            return self._get_fallback_decision(context)
    
    def _build_modality_decision_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for modality decision"""
        
        prompt = f"""Determine the optimal content modality transition strategy for a user experiencing network instability.

Current Context:
- Available Bandwidth: {context.get('available_bandwidth_kbps', 'unknown')} Kbps
- Predicted Signal Drop: {context.get('prediction_confidence', 0) * 100:.0f}% confidence in {context.get('time_to_signal_drop', 'unknown')}s
- Current Content: {context.get('content_description', 'educational video')}
- Content Timestamp: {context.get('content_position', 0):.1f}s
- Key Concepts: {', '.join(context.get('key_concepts', []))}
- Visual Dependency Score: {context.get('visual_dependency_score', 0.5):.2f}
- Current Modality: {context.get('current_modality', 'VIDEO')}

Historical Context:
- Recent Transitions: {', '.join(context.get('transition_history', []))}

Task: Determine the optimal content modality transition strategy.

Consider:
1. Will the user lose critical educational content if we transition?
2. Can the current concept be understood without video?
3. What is the minimum viable modality for this content segment?
4. How long will the network instability last?

Respond with JSON:
{{
  "target_modality": "VIDEO|AUDIO|TEXT_SUMMARY",
  "transition_timing": "IMMEDIATE|WAIT_2S|WAIT_5S",
  "reasoning": "explanation of decision",
  "fallback_strategy": "if primary strategy fails",
  "decision_confidence": 0.0-1.0
}}"""
        
        return prompt
    
    def _get_fallback_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get rule-based fallback decision when Bedrock unavailable
        
        Args:
            context: Decision context
            
        Returns:
            Fallback decision
        """
        bandwidth = context.get('available_bandwidth_kbps', 0)
        visual_dependency = context.get('visual_dependency_score', 0.5)
        
        # Simple rule-based logic
        if bandwidth >= 1000 and visual_dependency < 0.7:
            target_modality = "VIDEO"
            timing = "IMMEDIATE"
            reasoning = "Sufficient bandwidth and low visual dependency. Maintain video."
        elif bandwidth >= 500:
            target_modality = "AUDIO"
            timing = "WAIT_2S"
            reasoning = "Moderate bandwidth. Transition to audio after current segment."
        else:
            target_modality = "TEXT_SUMMARY"
            timing = "IMMEDIATE"
            reasoning = "Low bandwidth. Immediate transition to text summary."
        
        return {
            "target_modality": target_modality,
            "transition_timing": timing,
            "reasoning": reasoning + " [Fallback rule-based decision]",
            "fallback_strategy": "Continue with best-effort delivery",
            "decision_confidence": 0.6,
            "model_used": "rule-based-fallback"
        }
    
    def _get_mock_response(self, prompt: str) -> Dict[str, Any]:
        """Get mock response for testing without AWS credentials"""
        
        # Simple mock based on prompt content
        if "800" in prompt or "low" in prompt.lower():
            content = json.dumps({
                "target_modality": "AUDIO",
                "transition_timing": "WAIT_2S",
                "reasoning": "Bandwidth at 800 Kbps suggests audio modality. Waiting 2s to complete current concept.",
                "fallback_strategy": "If audio fails, transition to TEXT_SUMMARY",
                "decision_confidence": 0.85
            })
        else:
            content = json.dumps({
                "target_modality": "VIDEO",
                "transition_timing": "IMMEDIATE",
                "reasoning": "Sufficient bandwidth to maintain video quality.",
                "fallback_strategy": "Monitor for degradation",
                "decision_confidence": 0.90
            })
        
        return {
            "success": True,
            "content": content,
            "model": "mock-claude-3.5",
            "processing_time_ms": 300,
            "stop_reason": "end_turn"
        }
