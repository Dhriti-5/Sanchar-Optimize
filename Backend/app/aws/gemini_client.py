"""
Google Gemini Client
Fallback AI provider when Bedrock is unavailable
Provides identical interface to BedrockClient for seamless swapping
"""

import json
import logging
from typing import Dict, Any, Optional
import time

try:
    import google.generativeai as genai
    from google.api_core.exceptions import GoogleAPIError
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    GoogleAPIError = Exception

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Google Gemini API
    Provides fallback AI capabilities when Bedrock is unavailable
    Interface matches BedrockClient for transparent swapping
    """
    
    def __init__(self):
        """Initialize Gemini client with automatic model fallback"""
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL_ID
        self.max_tokens = settings.GEMINI_MAX_TOKENS
        self.temperature = settings.GEMINI_TEMPERATURE
        
        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai not installed. Gemini fallback unavailable.")
            self.client = None
            return
        
        if not self.api_key or self.api_key == "your-gemini-api-key-here":
            logger.warning("GEMINI_API_KEY not configured. Gemini fallback unavailable.")
            self.client = None
            return
        
        try:
            genai.configure(api_key=self.api_key)
            
            # Try multiple stable model names (without version suffixes that may not exist)
            # Use simple names - the API will handle the full path
            model_names_to_try = [
                self.model_name,  # Try configured model first
                "gemini-pro",  # Most stable production model
                "gemini-1.5-pro",  # Newer version
                "models/gemini-pro",  # Try with full path
            ]
            
            last_error = None
            for model_name in model_names_to_try:
                try:
                    self.client = genai.GenerativeModel(
                        model_name=model_name,
                        generation_config={
                            "max_output_tokens": self.max_tokens,
                            "temperature": self.temperature,
                        }
                    )
                    self.model_name = model_name  # Update to the working model
                    logger.info(f"Gemini client initialized with model {self.model_name}")
                    return
                except Exception as e:
                    last_error = e
                    logger.debug(f"Model {model_name} not available: {e}")
                    continue
            
            # If we get here, none of the models worked
            logger.error(f"Failed to initialize any Gemini model. Last error: {last_error}")
            self.client = None
            
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}")
            self.client = None
    
    async def invoke_model(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Invoke Gemini model with a prompt
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Model response as dictionary (compatible with Bedrock format)
        """
        if self.client is None:
            logger.error("Gemini client not available")
            return {
                "success": False,
                "error": "Gemini client not initialized",
                "fallback": False  # No further fallback available
            }
        
        try:
            start_time = time.time()
            
            # Combine system prompt and user prompt for Gemini
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Update generation config if custom values provided
            generation_config = {
                "max_output_tokens": max_tokens or self.max_tokens,
                "temperature": temperature or self.temperature,
            }
            
            # Generate response
            logger.info(f"Invoking Gemini model: {self.model_name}")
            response = self.client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract text from response
            if not response.parts:
                logger.error("Gemini returned empty response")
                return {
                    "success": False,
                    "error": "Empty response from Gemini",
                    "fallback": False
                }
            
            content_text = response.text
            
            logger.info(f"Gemini invocation successful: {processing_time_ms}ms "
                       f"({len(content_text)} chars)")
            
            return {
                "success": True,
                "content": content_text,
                "model": self.model_name,
                "processing_time_ms": processing_time_ms,
                "stop_reason": "stop",  # Gemini doesn't provide detailed stop reasons
                "provider": "gemini"
            }
            
        except GoogleAPIError as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "success": False,
                "error": f"Gemini API error: {str(e)}",
                "fallback": False
            }
        except AttributeError as e:
            # Handle case where response doesn't have expected attributes
            logger.error(f"Gemini response parsing error: {e}")
            return {
                "success": False,
                "error": f"Failed to parse Gemini response: {str(e)}",
                "fallback": False
            }
        except Exception as e:
            logger.error(f"Unexpected error invoking Gemini: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": False
            }
    
    async def get_modality_decision(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get modality transition decision from Gemini
        
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
2. Network constraints - adapt to bandwidth limitations
3. User experience - minimize disruption
4. Content type - some content requires visual elements

Respond with valid JSON only, no additional text, no markdown code blocks."""
        
        # Invoke Gemini
        response = await self.invoke_model(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent decisions
        )
        
        if response.get("success"):
            # Parse JSON response
            try:
                # Gemini sometimes wraps JSON in markdown code blocks
                content = response["content"].strip()
                if content.startswith("```json"):
                    content = content.replace("```json", "").replace("```", "").strip()
                elif content.startswith("```"):
                    content = content.replace("```", "").strip()
                
                decision = json.loads(content)
                decision["processing_time_ms"] = response.get("processing_time_ms")
                decision["ai_model_used"] = self.model_name
                return decision
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini JSON response: {e}")
                logger.error(f"Response content: {response.get('content', '')[:500]}")
                return self._get_fallback_decision(context)
        else:
            logger.warning("Gemini invocation failed. Using rule-based fallback.")
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

Respond with JSON only (no markdown formatting):
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
        Get rule-based fallback decision when AI unavailable
        
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
            "reasoning": reasoning,
            "fallback_strategy": "text_summary",
            "decision_confidence": 0.6,
            "ai_model_used": "rule-based-fallback",
            "processing_time_ms": 0
        }
