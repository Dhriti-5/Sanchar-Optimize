"""
Content Transformation API
Provides real AI summary generation for extension handshake flow
"""

from typing import List, Optional
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models.content import TransformationRequest
from app.services.multi_modal_transformer import MultiModalTransformer
from app.aws.s3_client import s3_client

logger = logging.getLogger(__name__)

router = APIRouter()
_transformer: MultiModalTransformer | None = None


class ExtensionSummaryRequest(BaseModel):
    video_id: str = Field(..., min_length=1)
    platform: str = Field(default="web")
    current_time: float = Field(default=0.0, ge=0.0)
    duration: Optional[float] = Field(default=None, gt=0.0)
    title: Optional[str] = None
    url: Optional[str] = None
    bandwidth_kbps: float = Field(default=800.0, ge=1.0)
    transcript_hint: Optional[str] = None
    visual_context_hint: Optional[str] = None
    key_concepts_hint: List[str] = Field(default_factory=list)
    include_images: bool = True


class ExtensionSummaryResponse(BaseModel):
    videoId: str
    timestamp: float
    keyConcepts: List[str]
    summary: str
    whatYouLearned: Optional[str] = None  # Content from before stop point
    whatsNext: Optional[str] = None  # Content coming after stop point
    visualDescriptions: List[str]
    keyFrame: Optional[dict] = None
    compressionRatio: float
    generatedBy: str
    generatedAt: float
    source: str
    contentUrl: Optional[str] = None


def get_transformer() -> MultiModalTransformer:
    global _transformer
    if _transformer is None:
        _transformer = MultiModalTransformer()
    return _transformer


@router.post("/content/summary", response_model=ExtensionSummaryResponse)
async def generate_extension_summary(request: ExtensionSummaryRequest):
    try:
        transformer = get_transformer()
        
        logger.info(f"📹 Summary request for {request.platform}:{request.video_id} at {request.current_time:.1f}s")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Has transcript_hint: {bool(request.transcript_hint)}")
        logger.info(f"   Transcript hint length: {len(request.transcript_hint) if request.transcript_hint else 0} chars")

        # Current segment (where video stopped) - INCREASED for better context
        segment_window = 60.0  # Increased from 45s to 60s for more context
        start_time = max(0.0, request.current_time - 15.0)  # Include 15s before for context
        end_time = start_time + segment_window
        if request.duration is not None:
            end_time = min(end_time, request.duration)
        if end_time <= start_time:
            end_time = start_time + 30.0  # Minimum 30s segment

        # Generate main content summary
        transform_request = TransformationRequest(
            content_id=f"{request.platform}_{request.video_id}",
            start_time=start_time,
            end_time=end_time,
            target_size_kb=32,
            include_images=request.include_images,
            priority="high",
            user_bandwidth_kbps=request.bandwidth_kbps,
            previous_position=start_time,
            transcript_hint=request.transcript_hint,
            visual_context_hint=request.visual_context_hint,
            key_concepts_hint=request.key_concepts_hint,
        )

        transformed = await transformer.transform_content(transform_request)

        # Generate "What You Learned" (30 seconds before stop point)
        what_you_learned = None
        if start_time > 30:
            past_prompt = f"""Summarize what was covered in the 30 seconds BEFORE timestamp {start_time:.0f}s. 
            This helps the learner understand what they just watched before the network dropped.
            Focus on completed concepts and key takeaways. Keep it brief (2-3 sentences)."""
            
            try:
                past_response = await transformer.bedrock_client.generate_with_caching(
                    prompt=past_prompt,
                    max_tokens=200
                )
                what_you_learned = past_response if past_response else "Review previous concepts when video resumes"
            except:
                what_you_learned = "Content from the last 30 seconds will be available when you resume"

        # Generate "What's Next" (30 seconds after current segment)
        whats_next = None
        next_start = end_time
        next_end = next_start + 30
        if request.duration is None or next_end <= request.duration:
            next_prompt = f"""Based on the educational content flow, predict what topics/concepts will likely be covered 
            in the next 30 seconds starting from timestamp {next_start:.0f}s. 
            This helps the learner know what to expect when they resume. 
            Keep it brief (2-3 sentences) and focus on upcoming concepts."""
            
            try:
                next_response = await transformer.bedrock_client.generate_with_caching(
                    prompt=next_prompt,
                    max_tokens=200
                )
                whats_next = next_response if next_response else "More concepts continue in the next segment"
            except:
                whats_next = "Continue watching to learn more advanced concepts"

        # Upload to S3
        content_url = transformed.content_url
        uploaded_url = await s3_client.upload_summary(
            transformed.summary.summary_id,
            transformed.summary.model_dump()
        )
        if uploaded_url:
            content_url = uploaded_url

        # Add key frame
        key_frame = None
        if transformed.summary.images:
            key_frame = {
                "url": transformed.summary.images[0],
                "format": "webp",
                "timestamp": start_time,
            }

        # Visual descriptions
        visual_descriptions = []
        if request.visual_context_hint:
            visual_descriptions.append(request.visual_context_hint)
        # Note: Summary model doesn't have visual_description field
        # Visual context is provided via request.visual_context_hint from extension

        return ExtensionSummaryResponse(
            videoId=request.video_id,
            timestamp=start_time,
            keyConcepts=transformed.summary.key_concepts,
            summary=transformed.summary.text,
            whatYouLearned=what_you_learned,
            whatsNext=whats_next,
            visualDescriptions=visual_descriptions,
            keyFrame=key_frame,
            compressionRatio=transformed.summary.compression_ratio,
            generatedBy=transformed.summary.ai_model_version,
            generatedAt=transformed.summary.generation_timestamp,
            source="bedrock" if transformed.summary.ai_model_version != "fallback" else "fallback",
            contentUrl=content_url,
        )
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        )


@router.get("/content/health")
async def content_health():
    transformer = get_transformer()
    return {
        "status": "healthy",
        "bedrock_available": transformer.bedrock_client.client is not None,
        "mock_enabled": bool(getattr(transformer.bedrock_client, "allow_mock_responses", False))
    }
