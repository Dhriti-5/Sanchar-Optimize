"""
Multi-Modal Transformer Service
RAG-based pipeline for intelligent content summarization
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import hashlib

from app.models.content import (
    ContentSegment,
    Summary,
    TransformationRequest,
    TransformationResponse,
    TranscriptCache
)
from app.aws.bedrock_client import BedrockClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class MultiModalTransformer:
    """
    Multi-Modal Transformer - RAG-based Content Summarization
    
    Responsibilities:
    - Extract video transcripts and visual context
    - Generate AI summaries using RAG pipeline
    - Compress content to <10% of original size
    - Maintain semantic alignment with original content
    - Generate concept images when bandwidth permits
    """
    
    def __init__(self, bedrock_client: Optional[BedrockClient] = None):
        """
        Initialize Multi-Modal Transformer
        
        Args:
            bedrock_client: Bedrock client instance (optional)
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        
        # In-memory caches (in production, use Redis/S3)
        self.transcript_cache: Dict[str, TranscriptCache] = {}
        self.summary_cache: Dict[str, Summary] = {}
        
        logger.info("Multi-Modal Transformer initialized")
    
    async def transform_content(
        self,
        request: TransformationRequest
    ) -> TransformationResponse:
        """
        Transform video content to AI-generated summary
        
        Args:
            request: Transformation request
            
        Returns:
            Transformation response with summary
        """
        try:
            start_time = datetime.now()
            
            logger.info(f"Transforming content {request.content_id}: "
                       f"{request.start_time:.1f}s - {request.end_time:.1f}s")
            
            # Check cache first
            cache_key = self._get_cache_key(request)
            cached_summary = self._get_cached_summary(cache_key)
            
            if cached_summary:
                logger.info(f"Cache hit for {cache_key}")
                generation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                return TransformationResponse(
                    summary=cached_summary,
                    content_url=f"s3://{settings.S3_BUCKET_NAME}/summaries/{cached_summary.summary_id}.json",
                    estimated_size_kb=self._estimate_summary_size(cached_summary),
                    generation_time_ms=generation_time_ms,
                    cache_hit=True
                )
            
            # Extract transcript for segment
            transcript = await self.extract_transcript(
                content_id=request.content_id,
                start_time=request.start_time,
                end_time=request.end_time
            )
            
            # Extract visual context
            visual_context = await self.extract_visual_context(
                content_id=request.content_id,
                timestamp=(request.start_time + request.end_time) / 2
            )
            
            # Build content segment
            segment = ContentSegment(
                content_id=request.content_id,
                start_time=request.start_time,
                end_time=request.end_time,
                transcript=transcript,
                has_visual_elements=visual_context.get("has_visual_elements", False),
                visual_description=visual_context.get("description"),
                key_concepts=visual_context.get("key_concepts", []),
                importance_score=0.8  # Default importance
            )
            
            # Generate summary using RAG pipeline
            summary = await self.generate_summary(segment, request)
            
            # Compress if needed
            if request.target_size_kb:
                summary = await self.compress_summary(summary, request.target_size_kb)
            
            # Cache the summary
            self._cache_summary(cache_key, summary)
            
            generation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            logger.info(f"Summary generated: {len(summary.text)} chars, "
                       f"compression={summary.compression_ratio:.2%}, "
                       f"coverage={summary.semantic_coverage_score:.2f}")
            
            return TransformationResponse(
                summary=summary,
                content_url=f"s3://{settings.S3_BUCKET_NAME}/summaries/{summary.summary_id}.json",
                estimated_size_kb=self._estimate_summary_size(summary),
                generation_time_ms=generation_time_ms,
                cache_hit=False
            )
            
        except Exception as e:
            logger.error(f"Content transformation failed: {e}")
            raise
    
    async def extract_transcript(
        self,
        content_id: str,
        start_time: float,
        end_time: float
    ) -> str:
        """
        Extract video transcript for specified time range
        
        Args:
            content_id: Content identifier
            start_time: Segment start time (seconds)
            end_time: Segment end time (seconds)
            
        Returns:
            Transcript text
        """
        # Check cache
        if content_id in self.transcript_cache:
            cached = self.transcript_cache[content_id]
            age = datetime.now().timestamp() - cached.cache_timestamp
            
            if age < cached.ttl_seconds:
                # Extract segment from full transcript
                # In production, this would use timestamp data
                logger.debug(f"Using cached transcript for {content_id}")
                return self._extract_segment_from_transcript(
                    cached.transcript,
                    start_time,
                    end_time
                )
        
        # In production: Call speech-to-text service or retrieve from database
        # For now, return mock transcript
        logger.warning(f"No cached transcript for {content_id}. Using mock.")
        
        mock_transcript = f"""
        [Educational content from {start_time:.1f}s to {end_time:.1f}s]
        
        In this section, we explore fundamental concepts that are essential for understanding 
        the topic. The key points covered include the definition of core terms, practical 
        applications, and real-world examples that illustrate the concepts clearly.
        
        We begin by examining the theoretical foundation, then move to practical demonstrations 
        that show how these principles work in practice. This approach helps build intuition 
        while maintaining rigor.
        
        The visual elements accompanying this section include diagrams showing the relationship 
        between different components, graphs illustrating key trends, and step-by-step 
        walkthroughs of example problems.
        """
        
        # Cache the transcript
        self.transcript_cache[content_id] = TranscriptCache(
            content_id=content_id,
            transcript=mock_transcript,
            timestamps=[],
            ttl_seconds=settings.TRANSCRIPT_CACHE_TTL_SECONDS
        )
        
        return mock_transcript
    
    async def extract_visual_context(
        self,
        content_id: str,
        timestamp: float
    ) -> Dict[str, Any]:
        """
        Extract visual context from video frames
        
        Args:
            content_id: Content identifier
            timestamp: Timestamp to analyze
            
        Returns:
            Visual context dictionary
        """
        # In production: Use computer vision to analyze frames
        # For now, return mock visual context
        
        logger.debug(f"Extracting visual context for {content_id} at {timestamp:.1f}s")
        
        return {
            "has_visual_elements": True,
            "description": "Video contains diagrams and equations on whiteboard",
            "key_concepts": ["mathematical formulas", "step-by-step derivation", "graph visualization"],
            "visual_dependency_score": 0.7
        }
    
    async def generate_summary(
        self,
        segment: ContentSegment,
        request: TransformationRequest
    ) -> Summary:
        """
        Generate AI summary using RAG pipeline
        
        Args:
            segment: Content segment with transcript
            request: Original transformation request
            
        Returns:
            Generated summary
        """
        # Build RAG prompt
        prompt = self._build_rag_prompt(segment, request)
        
        system_prompt = """You are an expert educational content summarizer. Your role is to create concise, accurate summaries of educational video content that preserve all critical learning concepts while dramatically reducing size.

Guidelines:
1. Extract and explain all key concepts
2. Preserve essential definitions, formulas, and examples
3. Maintain logical flow and structure
4. Use clear, educational language
5. Be concise but complete

Respond with valid JSON only."""
        
        # Get summary from Bedrock
        response = await self.bedrock_client.invoke_model(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3
        )
        
        if response.get("success"):
            # Parse summary JSON
            try:
                summary_data = json.loads(response["content"])
                
                # Calculate metrics
                original_size = len(segment.transcript) if segment.transcript else 1000
                summary_size = len(summary_data.get("text", ""))
                compression_ratio = summary_size / original_size
                
                # Create summary object
                summary = Summary(
                    content_id=segment.content_id,
                    segment_id=segment.segment_id,
                    text=summary_data.get("text", ""),
                    key_concepts=summary_data.get("key_concepts", []),
                    key_points=summary_data.get("key_points", []),
                    images=[],  # Would be generated separately
                    diagrams=[],
                    original_duration_seconds=segment.end_time - segment.start_time,
                    compression_ratio=compression_ratio,
                    semantic_coverage_score=summary_data.get("coverage_score", 0.85)
                )
                
                return summary
                
            except json.JSONDecodeError:
                logger.error("Failed to parse Bedrock summary JSON")
                return self._get_fallback_summary(segment)
        else:
            logger.warning("Bedrock summary generation failed. Using fallback.")
            return self._get_fallback_summary(segment)
    
    async def compress_summary(
        self,
        summary: Summary,
        target_size_kb: int
    ) -> Summary:
        """
        Compress summary to target size
        
        Args:
            summary: Original summary
            target_size_kb: Target size in KB
            
        Returns:
            Compressed summary
        """
        current_size_kb = len(summary.text.encode('utf-8')) / 1024
        
        if current_size_kb <= target_size_kb:
            return summary  # Already small enough
        
        # Calculate compression ratio needed
        ratio = target_size_kb / current_size_kb
        target_chars = int(len(summary.text) * ratio)
        
        logger.info(f"Compressing summary from {current_size_kb:.1f}KB to {target_size_kb}KB")
        
        # Intelligently compress (in production, use Bedrock to rewrite more concisely)
        # For now, simple truncation with ellipsis
        compressed_text = summary.text[:target_chars-3] + "..."
        
        summary.text = compressed_text
        summary.compression_ratio = len(compressed_text) / len(summary.text)
        
        return summary
    
    async def generate_concept_image(
        self,
        concept: str,
        context: str
    ) -> str:
        """
        Generate AI image illustrating a key concept
        
        Args:
            concept: The concept to illustrate
            context: Context for the concept
            
        Returns:
            Image URL (S3 or generated)
        """
        # In production: Use Amazon Bedrock image generation
        # For now, return placeholder
        
        logger.info(f"Would generate image for concept: {concept}")
        
        image_id = hashlib.md5(f"{concept}:{context}".encode()).hexdigest()[:12]
        return f"s3://{settings.S3_BUCKET_NAME}/images/{image_id}.png"
    
    def _build_rag_prompt(
        self,
        segment: ContentSegment,
        request: TransformationRequest
    ) -> str:
        """Build RAG prompt for summary generation"""
        
        prompt = f"""Generate a concise educational summary of the following video segment.

Video Segment ({segment.start_time:.1f}s - {segment.end_time:.1f}s):
{segment.transcript}

Visual Elements:
{segment.visual_description or 'No special visual elements'}

User Context:
- Current Bandwidth: {request.user_bandwidth_kbps:.0f} Kbps
- Target Size: {request.target_size_kb or 'flexible'} KB
- Priority: {request.priority}

Task: Create a summary that:
1. Preserves all critical learning concepts
2. Maintains educational value
3. Is dramatically smaller than original (aim for <10% of original size)
4. Can be understood without the video

Respond with JSON:
{{
  "text": "Full summary text with all key concepts explained",
  "key_concepts": ["concept1", "concept2", "concept3"],
  "key_points": ["point 1", "point 2", "point 3"],
  "coverage_score": 0.0-1.0
}}"""
        
        return prompt
    
    def _get_fallback_summary(self, segment: ContentSegment) -> Summary:
        """Get fallback summary when AI fails"""
        
        # Extract first few sentences as summary
        transcript = segment.transcript or ""
        sentences = transcript.split('.')[:3]
        fallback_text = '. '.join(sentences) + '.'
        
        return Summary(
            content_id=segment.content_id,
            segment_id=segment.segment_id,
            text=fallback_text + " [Fallback summary - AI generation unavailable]",
            key_concepts=segment.key_concepts or [],
            key_points=[],
            images=[],
            diagrams=[],
            original_duration_seconds=segment.end_time - segment.start_time,
            compression_ratio=len(fallback_text) / max(len(transcript), 100),
            semantic_coverage_score=0.5,
            model_version="fallback"
        )
    
    def _extract_segment_from_transcript(
        self,
        full_transcript: str,
        start_time: float,
        end_time: float
    ) -> str:
        """Extract segment from full transcript based on timestamps"""
        
        # In production, this would use timestamp data to extract precise segment
        # For now, estimate based on position
        
        # Simple estimation: assume uniform distribution
        duration_ratio = (end_time - start_time) / 600  # Assume 10min video
        start_pos = int(len(full_transcript) * (start_time / 600))
        end_pos = int(len(full_transcript) * (end_time / 600))
        
        segment = full_transcript[start_pos:end_pos]
        return segment if segment else full_transcript
    
    def _get_cache_key(self, request: TransformationRequest) -> str:
        """Generate cache key for request"""
        key_data = f"{request.content_id}:{request.start_time}:{request.end_time}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_summary(self, cache_key: str) -> Optional[Summary]:
        """Get cached summary if available"""
        return self.summary_cache.get(cache_key)
    
    def _cache_summary(self, cache_key: str, summary: Summary):
        """Cache a summary"""
        self.summary_cache[cache_key] = summary
        
        # Limit cache size
        if len(self.summary_cache) > 1000:
            # Remove oldest entries
            oldest_keys = list(self.summary_cache.keys())[:100]
            for key in oldest_keys:
                del self.summary_cache[key]
    
    def _estimate_summary_size(self, summary: Summary) -> float:
        """Estimate summary size in KB"""
        text_size = len(summary.text.encode('utf-8'))
        metadata_size = len(json.dumps({
            "key_concepts": summary.key_concepts,
            "key_points": summary.key_points
        }).encode('utf-8'))
        
        total_size_bytes = text_size + metadata_size
        return total_size_bytes / 1024
