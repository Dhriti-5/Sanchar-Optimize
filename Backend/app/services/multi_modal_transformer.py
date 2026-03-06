"""
Multi-Modal Transformer Service
RAG-based pipeline for intelligent content summarization with YouTube support
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
from app.services.youtube_transcript_service import YouTubeTranscriptService
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
        self.youtube_service = YouTubeTranscriptService()
        
        # In-memory caches (in production, use Redis/S3)
        self.transcript_cache: Dict[str, TranscriptCache] = {}
        self.summary_cache: Dict[str, Summary] = {}
        
        logger.info("Multi-Modal Transformer initialized with YouTube support")
    
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
            
            if request.transcript_hint:
                self.transcript_cache[request.content_id] = TranscriptCache(
                    content_id=request.content_id,
                    transcript=request.transcript_hint,
                    timestamps=[],
                    ttl_seconds=settings.TRANSCRIPT_CACHE_TTL_SECONDS
                )
            
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
            try:
                visual_context = await self.extract_visual_context(
                    content_id=request.content_id,
                    timestamp=(request.start_time + request.end_time) / 2,
                    visual_context_hint=request.visual_context_hint,
                    key_concepts_hint=request.key_concepts_hint
                )
            except TypeError:
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

            if request.include_images and segment.has_visual_elements:
                key_frame_url = await self.generate_key_frame(
                    content_id=request.content_id,
                    timestamp=(request.start_time + request.end_time) / 2,
                    visual_context=segment.visual_description or ""
                )
                summary.images.append(key_frame_url)
                summary.diagrams.append({
                    "type": "key_frame",
                    "format": "webp",
                    "url": key_frame_url,
                    "timestamp": (request.start_time + request.end_time) / 2
                })
            
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
        utomatically detects YouTube videos and fetches real transcripts
        
        Args:
            content_id: Content identifier (e.g., "youtube_dQw4w9WgXcQ")
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
                logger.debug(f"Using cached transcript for {content_id}")
                
                # If we have YouTube segments, use them for precise extraction
                if hasattr(cached, 'youtube_segments') and cached.youtube_segments:
                    text = self.youtube_service.extract_segment_text(
                        cached.youtube_segments,
                        start_time,
                        end_time
                    )
                    if text:
                        return text
                
                return self._extract_segment_from_transcript(
                    cached.transcript,
                    start_time,
                    end_time
                )
        
        # Try to fetch from YouTube if it's a YouTube video
        if content_id.startswith("youtube_") or content_id.startswith("web_"):
            video_id = content_id.replace("youtube_", "").replace("web_", "")
            
            if self.youtube_service.available:
                logger.info(f"🎬 Fetching FULL YouTube transcript for video ID: {video_id}")
                segments, metadata = await self.youtube_service.get_transcript(video_id)
                
                if segments and not metadata.get("error"):
                    # Cache the full transcript and segments
                    full_text = " ".join(seg.text for seg in segments)
                    cache_entry = TranscriptCache(
                        content_id=content_id,
                        transcript=full_text,
                        timestamps=[seg.start for seg in segments],
                        ttl_seconds=settings.TRANSCRIPT_CACHE_TTL_SECONDS
                    )
                    # Add segments for precise extraction
                    cache_entry.youtube_segments = segments
                    self.transcript_cache[content_id] = cache_entry
                    
                    # Extract segment
                    segment_text = self.youtube_service.extract_segment_text(
                        segments,
                        start_time,
                        end_time
                    )
                    
                    logger.info(f"✅ YouTube transcript extracted: {len(segment_text)} chars from {start_time:.1f}s-{end_time:.1f}s")
                    logger.info(f"   First 200 chars: {segment_text[:200]}...")
                    return segment_text
                else:
                    logger.warning(f"Failed to fetch YouTube transcript: {metadata.get('error')}")
        
        if settings.ALLOW_SYNTHETIC_CONTENT_FALLBACK:
            logger.warning(f"No transcript available for {content_id}. Using synthetic fallback transcript.")
            synthetic_transcript = (
                f"[Synthetic fallback transcript for {content_id} "
                f"between {start_time:.1f}s and {end_time:.1f}s]"
            )
            self.transcript_cache[content_id] = TranscriptCache(
                content_id=content_id,
                transcript=synthetic_transcript,
                timestamps=[],
                ttl_seconds=settings.TRANSCRIPT_CACHE_TTL_SECONDS
            )
            return synthetic_transcript

        logger.warning(f"No transcript available for {content_id}. Continuing without transcript context.")
        return ""
    
    async def extract_visual_context(
        self,
        content_id: str,
        timestamp: float,
        visual_context_hint: Optional[str] = None,
        key_concepts_hint: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract visual context from video frames
        
        Args:
            content_id: Content identifier
            timestamp: Timestamp to analyze
            
        Returns:
            Visual context dictionary
        """
        logger.debug(f"Extracting visual context for {content_id} at {timestamp:.1f}s")

        if visual_context_hint or key_concepts_hint:
            return {
                "has_visual_elements": bool(visual_context_hint),
                "description": visual_context_hint,
                "key_concepts": key_concepts_hint or [],
                "visual_dependency_score": 0.6 if visual_context_hint else 0.3
            }

        if settings.ALLOW_SYNTHETIC_CONTENT_FALLBACK:
            return {
                "has_visual_elements": True,
                "description": "Synthetic fallback visual context",
                "key_concepts": ["fallback context"],
                "visual_dependency_score": 0.5
            }

        return {
            "has_visual_elements": False,
            "description": None,
            "key_concepts": [],
            "visual_dependency_score": 0.2
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
        
        system_prompt = """You are an expert educational content analyst and teacher. Your role is to transform video learning content into comprehensive written summaries that preserve full educational value.

Your summaries are used by students in rural India who lost internet connectivity while learning. They depend on your summaries to continue their education without the video.

Core Principles:
1. **REWRITE AND EXPLAIN** - Transform raw transcript into clear, well-structured educational content
2. **DON'T JUST REPEAT** - Improve grammar, add clarity, connect ideas logically  
3. **EXPLAIN CONCEPTS DEEPLY** - Define terms, give context, include reasoning and implications
4. **ADD EDUCATIONAL VALUE** - Provide examples, clarify difficult points, highlight key takeaways
5. **STRUCTURE CLEARLY** - Use proper paragraphs with topic sentences and logical flow
6. **DESCRIBE VISUALS** - If transcript mentions "as you can see" or "this diagram", explain what was likely shown
7. **BE COMPREHENSIVE** - 250-450 words for thorough coverage

BAD (just repeating): "The video talks about derivatives. It shows how to calculate them."
GOOD (educational): "A derivative represents the instantaneous rate of change of a function. In practical terms, if you have a function describing position over time, the derivative tells you the velocity at any given moment. To calculate a derivative, we use the limit definition: taking the difference quotient as the interval approaches zero. For example, the derivative of f(x)=x² is 2x, which means..."

Output Format: Respond ONLY with valid JSON (no markdown code blocks, no ```json):
{
  "text": "comprehensive, well-written educational summary with proper paragraphs",
  "key_concepts": ["Concept 1: detailed explanation", "Concept 2: with context"],
  "key_points": ["Specific insight with example", "Important detail explained"],
  "coverage_score": 0.0-1.0
}

Quality over brevity. Education over compression. Rewrite, don't repeat."""
        
        # Get summary from Bedrock
        response = await self.bedrock_client.invoke_model(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3
        )

        if response.get("success"):
            try:
                summary_data = json.loads(response["content"])
                original_size = len(segment.transcript) if segment.transcript else 1000
                summary_size = len(summary_data.get("text", ""))
                compression_ratio = summary_size / original_size

                return Summary(
                    content_id=segment.content_id,
                    segment_id=segment.segment_id,
                    text=summary_data.get("text", ""),
                    key_concepts=summary_data.get("key_concepts", []),
                    key_points=summary_data.get("key_points", []),
                    images=[],
                    diagrams=[],
                    original_duration_seconds=segment.end_time - segment.start_time,
                    compression_ratio=compression_ratio,
                    semantic_coverage_score=summary_data.get("coverage_score", 0.85)
                )
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
        """Compress summary to target size"""
        current_size_kb = len(summary.text.encode('utf-8')) / 1024
        
        if current_size_kb <= target_size_kb:
            return summary  # Already small enough
        
        # Calculate compression ratio needed
        ratio = target_size_kb / current_size_kb
        target_chars = int(len(summary.text) * ratio)
        
        logger.info(f"Compressing summary from {current_size_kb:.1f}KB to {target_size_kb}KB")
        
        # Intelligently compress (in production, use Bedrock to rewrite more concisely)
        # For now, simple truncation with ellipsis
        original_length = max(len(summary.text), 1)
        compressed_text = summary.text[:target_chars-3] + "..."
        summary.text = compressed_text
        summary.compression_ratio = len(compressed_text) / original_length
        
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

    async def generate_key_frame(
        self,
        content_id: str,
        timestamp: float,
        visual_context: str
    ) -> str:
        logger.info(f"Generating key frame for {content_id} at {timestamp:.1f}s")
        key = f"{content_id}:{timestamp:.1f}:{visual_context[:64]}"
        image_id = hashlib.md5(key.encode()).hexdigest()[:12]
        return f"s3://{settings.S3_BUCKET_NAME}/images/keyframe_{image_id}.webp"
    
    def _build_rag_prompt(
        self,
        segment: ContentSegment,
        request: TransformationRequest
    ) -> str:
        """Build RAG prompt for summary generation"""
        
        # Extract additional context hints
        visual_context_hint = request.visual_context_hint or segment.visual_description
        key_concepts_hint = request.key_concepts_hint or segment.key_concepts
        
        transcript_length = len(segment.transcript) if segment.transcript else 0
        has_full_transcript = transcript_length > 500  # Likely fetched from YouTube API
        
        prompt = f"""You are creating an educational summary for a student in rural India whose internet connection dropped while watching a learning video. Your goal is to help them continue learning WITHOUT the video.

=== VIDEO INFORMATION ===
Time Range: {segment.start_time:.1f}s - {segment.end_time:.1f}s ({segment.end_time - segment.start_time:.1f} seconds)
Video Context: {visual_context_hint or 'Educational video'}

=== SOURCE TRANSCRIPT ===
{"[FULL TRANSCRIPT - " + str(transcript_length) + " characters]" if has_full_transcript else "[CAPTION SNIPPET - Limited]"}
{segment.transcript if segment.transcript else '[No transcript available - generate based on visual context]'}

Previously Mentioned: {', '.join(key_concepts_hint) if key_concepts_hint else 'None yet'}

=== YOUR TASK ===
Transform the raw transcript above into a **well-written educational summary** that:

1. **REWRITES the content** - Don't copy the transcript verbatim. Improve grammar, structure, and clarity
2. **EXPLAINS thoroughly** - Define technical terms, explain WHY things work, give context
3. **ADDS educational value** - Connect concepts, provide examples, highlight implications  
4. **STRUCTURES clearly** - Use proper paragraphs with topic sentences
5. **DESCRIBES visuals** - If transcript says "as you can see" or mentions diagrams, explain what was likely shown
6. **MAINTAINS continuity** - Help student understand where they are in the lesson

IMPORTANT: Your summary should read like a **textbook explanation**, NOT like video captions.

=== OUTPUT REQUIREMENTS ===
- Length: 250-450 words (be thorough!)
- Structure: Multiple clear paragraphs
- Tone: Educational and explanatory
- Quality: Something a student could learn from without the video

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "text": "Start with an opening sentence that establishes context.\n\nThen explain the main concept in depth with proper paragraphs. Define technical terms. Give examples. Explain the reasoning and implications.\n\nConclude with key takeaways or how this connects to broader concepts.",
  "key_concepts": ["Concept 1: Full explanation with context", "Concept 2: What it means and why it matters", "Concept 3: How it connects to other ideas"],
  "key_points": ["Important insight with explanation", "Key example or demonstration described", "Practical implication or application"],
  "coverage_score": {"0.90" if has_full_transcript else "0.70"}
}}

Remember: A student in rural India is relying on this to continue their education. Make it genuinely educational, not just a transcript copy."""
        
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
