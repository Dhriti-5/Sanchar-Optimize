"""
Amazon Bedrock Client with Gemini Fallback
Handles interactions with Amazon Bedrock for AI-powered decisions
Automatically falls back to Google Gemini when Bedrock is unavailable
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
    Client for Amazon Bedrock API with Gemini Fallback
    
    Handles invocations of Claude 3.5 Sonnet for modality decisions.
    Automatically falls back to Google Gemini 1.5 Flash when Bedrock fails
    (AccessDeniedException, quota errors, etc.) - completely transparent to users.
    """
    
    def __init__(self):
        """Initialize Bedrock client with Gemini fallback"""
        self.allow_mock_responses = settings.BEDROCK_ALLOW_MOCK_RESPONSES
        self._gemini_client = None  # Lazy initialization
        self._fallback_active = False
        
        if boto3 is None:
            if self.allow_mock_responses:
                logger.warning("boto3 not installed. Bedrock client will use mock responses (BEDROCK_ALLOW_MOCK_RESPONSES=true).")
            else:
                logger.error("boto3 not installed. Bedrock client unavailable and mock responses disabled.")
            self.client = None
        else:
            try:
                # In Lambda, use IAM role credentials automatically
                import os
                is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
                
                client_kwargs = {'region_name': settings.AWS_REGION}
                
                # Only use explicit credentials if not in Lambda and they are set
                if not is_lambda and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                    client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                    client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
                
                self.client = boto3.client('bedrock-runtime', **client_kwargs)
                logger.info(f"Bedrock client initialized for region {settings.AWS_REGION}")
            except Exception as e:
                logger.error(f"Failed to initialize Bedrock client: {e}")
                self.client = None
        
        self.model_id = settings.BEDROCK_MODEL_ID
        self.max_tokens = settings.BEDROCK_MAX_TOKENS
        self.temperature = settings.BEDROCK_TEMPERATURE
    
    def _get_gemini_fallback(self):
        """Lazy initialization of Gemini client for fallback"""
        if self._gemini_client is None:
            try:
                from app.aws.gemini_client import GeminiClient
                self._gemini_client = GeminiClient()
                logger.info("Gemini fallback client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini fallback: {e}")
                self._gemini_client = None
        return self._gemini_client
    
    async def invoke_model(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Invoke Bedrock model with a prompt, automatically fall back to Gemini if needed
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Model response as dictionary
        """
        if self.client is None:
            if self.allow_mock_responses:
                logger.warning("Bedrock client not available. Using mock response (BEDROCK_ALLOW_MOCK_RESPONSES=true).")
                return self._get_mock_response(prompt)
            
            # Try Gemini fallback
            logger.info("Bedrock unavailable, attempting Gemini fallback")
            return await self._try_gemini_fallback(prompt, system_prompt, max_tokens, temperature)
        
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
            
            # Reset fallback flag on success
            if self._fallback_active:
                logger.info("Bedrock recovered, disabling fallback mode")
                self._fallback_active = False
            
            return {
                "success": True,
                "content": response_body['content'][0]['text'],
                "model": self.model_id,
                "processing_time_ms": processing_time_ms,
                "stop_reason": response_body.get('stop_reason', 'end_turn'),
                "provider": "bedrock"
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_msg = str(e)
            
            # Check for specific error types that should trigger fallback
            if error_code in ['AccessDeniedException', 'ThrottlingException', 'ServiceQuotaExceededException', 
                             'ModelNotReadyException', 'ValidationException']:
                logger.warning(f"Bedrock error ({error_code}), falling back to Gemini: {error_msg}")
                self._fallback_active = True
                return await self._try_gemini_fallback(prompt, system_prompt, max_tokens, temperature)
            
            logger.error(f"Bedrock API error: {e}")
            # Try fallback anyway
            return await self._try_gemini_fallback(prompt, system_prompt, max_tokens, temperature)
            
        except Exception as e:
            logger.error(f"Unexpected error invoking Bedrock: {e}")
            # Try fallback
            return await self._try_gemini_fallback(prompt, system_prompt, max_tokens, temperature)
    
    async def _try_gemini_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Attempt to use Gemini as fallback"""
        gemini = self._get_gemini_fallback()
        
        if gemini is None or gemini.client is None:
            logger.error("Gemini fallback not available")
            return {
                "success": False,
                "error": "Both Bedrock and Gemini unavailable",
                "fallback": False
            }
        
        logger.info("Using Gemini fallback for AI generation")
        result = await gemini.invoke_model(prompt, system_prompt, max_tokens, temperature)
        
        if result.get("success"):
            logger.info("Gemini fallback successful")
        
        return result
    
    async def get_modality_decision(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get modality transition decision from Bedrock (with Gemini fallback)
        
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
        
        # Invoke Bedrock (will auto-fallback to Gemini if needed)
        response = await self.invoke_model(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent decisions
        )
        
        if response.get("success"):
            # Parse JSON response
            try:
                content = response["content"].strip()
                # Handle markdown code blocks that Gemini might add
                if content.startswith("```json"):
                    content = content.replace("```json", "").replace("```", "").strip()
                elif content.startswith("```"):
                    content = content.replace("```", "").strip()
                
                decision = json.loads(content)
                decision["processing_time_ms"] = response.get("processing_time_ms")
                decision["ai_model_used"] = response.get("model", "unknown")
                decision["provider"] = response.get("provider", "unknown")
                return decision
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI JSON response: {e}")
                return self._get_fallback_decision(context)
        else:
            logger.warning("AI invocation failed. Using rule-based fallback.")
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
            "ai_model_used": "rule-based-fallback"
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
