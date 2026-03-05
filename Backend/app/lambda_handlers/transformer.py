"""
Lambda Handler for Multi-Modal Transformer
Generates AI summaries of video content for text fallback modality
"""

import json
import logging
import os
from typing import Any, Dict

from app.services.multi_modal_transformer import MultiModalTransformer
from app.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Multi-Modal content transformation.
    
    Expected event structure:
    {
        "device_id": "string",
        "content_id": "string",
        "content_title": "string",
        "transcript_hint": "string (partial transcript from video)",
        "visual_context_hint": "string (description of visual elements)",
        "key_concepts_hint": ["concept1", "concept2"],
        "start_time": float (seconds),
        "end_time": float (seconds),
        "max_summary_words": int (optional, default 150)
    }
    
    Returns:
    {
        "summary": {
            "text": "AI-generated summary",
            "key_concepts": ["concept1", "concept2"],
            "key_points": ["point1", "point2"],
            "coverage_score": float (0-1)
        },
        "compression_ratio": float (0-1),
        "generated_by": "bedrock",
        "source": "transformer"
    }
    """
    try:
        device_id = event.get("device_id", "lambda")
        content_id = event.get("content_id", "")
        content_title = event.get("content_title", "")
        transcript_hint = event.get("transcript_hint", "")
        visual_context_hint = event.get("visual_context_hint", "")
        key_concepts_hint = event.get("key_concepts_hint", [])
        start_time = event.get("start_time", 0)
        end_time = event.get("end_time", 60)
        max_words = event.get("max_summary_words", 150)
        
        if not content_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing content_id"})
            }
        
        # Create transformer
        transformer = MultiModalTransformer()
        
        # Build prompt for Bedrock
        prompt = f"""
You are an educational content summarizer. Generate a concise but complete summary 
of the video segment below for a student experiencing network issues.

Content Title: {content_title}
Duration: {start_time:.1f}s - {end_time:.1f}s

Transcript:
{transcript_hint or "No transcript available"}

Visual Elements:
{visual_context_hint or "No visual description available"}

Key Concepts to Cover:
{", ".join(key_concepts_hint) if key_concepts_hint else "Auto-detect from transcript"}

Requirements:
1. Extract key concepts and their definitions
2. Preserve all critical learning content
3. Describe visual demonstrations
4. Keep under {max_words} words
5. Format as JSON

Output format:
{{
  "summary": "concise narrative summary",
  "key_concepts": ["concept1: definition1", "concept2: definition2"],
  "key_points": ["point1", "point2", "point3"]
}}
"""
        
        try:
            # Invoke Bedrock if available
            if transformer.bedrock_client and transformer.bedrock_client.client:
                response = transformer.bedrock_client.invoke_model(prompt)
                
                if response.get("success"):
                    result = json.loads(response.get("text", "{}"))
                    summary_text = result.get("summary", "")
                    key_concepts = result.get("key_concepts", [])
                    key_points = result.get("key_points", [])
                    
                    # Calculate compression ratio
                    original_length = len((transcript_hint or "") + (visual_context_hint or ""))
                    summary_length = len(summary_text)
                    compression_ratio = 1 - (summary_length / max(original_length, 1))
                    
                    logger.info(
                        f"Summary generated for {device_id}/{content_id}: "
                        f"compression={compression_ratio:.2%}"
                    )
                    
                    return {
                        "statusCode": 200,
                        "body": json.dumps({
                            "summary": {
                                "text": summary_text,
                                "key_concepts": key_concepts,
                                "key_points": key_points,
                                "coverage_score": 0.9  # Estimated coverage
                            },
                            "compression_ratio": round(compression_ratio, 3),
                            "generated_by": "bedrock",
                            "source": "transformer",
                            "device_id": device_id
                        })
                    }
        except Exception as bed_error:
            logger.warning(f"Bedrock invocation failed: {str(bed_error)}")
        
        # Fallback: generate simple summary from hints
        if settings.ALLOW_SYNTHETIC_CONTENT_FALLBACK:
            summary_text = f"Summary of {content_title}: {transcript_hint[:200]}..."
            key_concepts = key_concepts_hint or ["concept1", "concept2"]
            key_points = ["Key point 1", "Key point 2", "Key point 3"]
            
            logger.info(
                f"Fallback summary for {device_id}/{content_id} "
                "(Bedrock unavailable)"
            )
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "summary": {
                        "text": summary_text,
                        "key_concepts": key_concepts,
                        "key_points": key_points,
                        "coverage_score": 0.6
                    },
                    "compression_ratio": 0.85,
                    "generated_by": "fallback",
                    "source": "transformer"
                })
            }
        else:
            return {
                "statusCode": 503,
                "body": json.dumps({
                    "error": "Content transformation unavailable (Bedrock not configured)",
                    "fallback_enabled": False
                })
            }
        
    except Exception as e:
        logger.error(f"Error in Transformer handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
