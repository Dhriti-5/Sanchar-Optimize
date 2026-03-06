"""
YouTube Educational Content API
Semantic chunking and "Continue Learning" support for network drops
"""

from typing import List, Optional
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.youtube_transcript_service import YouTubeTranscriptService, SemanticChunk
from app.services.multi_modal_transformer import MultiModalTransformer
from app.models.content import TransformationRequest

logger = logging.getLogger(__name__)

router = APIRouter()
_youtube_service: YouTubeTranscriptService | None = None
_transformer: MultiModalTransformer | None = None


class YouTubeTranscriptRequest(BaseModel):
    video_id: str = Field(..., description="YouTube video ID or URL")
    languages: Optional[List[str]] = Field(default=None, description="Preferred languages (e.g., ['en', 'hi'])")


class YouTubeSummaryRequest(BaseModel):
    video_id: str = Field(..., description="YouTube video ID or URL")
    current_timestamp: float = Field(..., description="Current playback position (seconds)")
    generate_full_chunk: bool = Field(default=True, description="Generate AI summary for the chunk")
    languages: Optional[List[str]] = Field(default=None)


class TranscriptSegmentResponse(BaseModel):
    text: str
    start: float
    end: float
    duration: float
    segment_id: int


class SemanticChunkResponse(BaseModel):
    chunk_id: int
    start_time: float
    end_time: float
    duration: float
    text: str
    segment_count: int
    ai_summary: Optional[str] = None
    key_concepts: Optional[List[str]] = None
    key_points: Optional[List[str]] = None


class YouTubeTranscriptResponse(BaseModel):
    video_id: str
    total_segments: int
    total_duration: float
    language: str
    chunks: List[SemanticChunkResponse]
    message: str


class ContinueLearningResponse(BaseModel):
    video_id: str
    current_timestamp: float
    relevant_chunk: SemanticChunkResponse
    previous_chunk: Optional[SemanticChunkResponse] = None
    next_chunk: Optional[SemanticChunkResponse] = None
    message: str


def get_youtube_service() -> YouTubeTranscriptService:
    global _youtube_service
    if _youtube_service is None:
        _youtube_service = YouTubeTranscriptService()
    return _youtube_service


def get_transformer() -> MultiModalTransformer:
    global _transformer
    if _transformer is None:
        _transformer = MultiModalTransformer()
    return _transformer


@router.post("/youtube/transcript", response_model=YouTubeTranscriptResponse)
async def get_youtube_transcript(request: YouTubeTranscriptRequest):
    """
    Extract full YouTube transcript with semantic chunking
    
    Returns transcript divided into 2-3 minute learning blocks,
    perfect for "continue learning" feature during network drops.
    """
    try:
        service = get_youtube_service()
        
        if not service.available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube transcript service not available. Install youtube-transcript-api."
            )
        
        # Extract transcript
        segments, metadata = await service.get_transcript(
            request.video_id,
            languages=request.languages
        )
        
        if metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=metadata["error"]
            )
        
        # Create semantic chunks
        chunks = service.create_semantic_chunks(segments)
        
        # Convert to response format
        chunk_responses = [
            SemanticChunkResponse(
                chunk_id=chunk.chunk_id,
                start_time=chunk.start_time,
                end_time=chunk.end_time,
                duration=chunk.duration,
                text=chunk.text,
                segment_count=len(chunk.segments)
            )
            for chunk in chunks
        ]
        
        return YouTubeTranscriptResponse(
            video_id=metadata["video_id"],
            total_segments=metadata["segment_count"],
            total_duration=metadata["total_duration"],
            language=metadata["language"],
            chunks=chunk_responses,
            message=f"Extracted {len(chunks)} semantic learning blocks from video"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract YouTube transcript: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract transcript: {str(e)}"
        )


@router.post("/youtube/continue-learning", response_model=ContinueLearningResponse)
async def get_continue_learning_summary(request: YouTubeSummaryRequest):
    """
    Get "Continue Learning" summary for network drop scenario
    
    When a student loses internet, this returns:
    1. The relevant learning chunk for their current timestamp
    2. AI-generated summary so they can keep learning
    3. Context from previous/next chunks
    
    Perfect for the jury demo: "Network dropped at 2:34, but student
    can still learn from the AI summary of that exact section!"
    """
    try:
        youtube_service = get_youtube_service()
        transformer = get_transformer()
        
        if not youtube_service.available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube transcript service not available"
            )
        
        # Extract transcript and create chunks
        segments, metadata = await youtube_service.get_transcript(
            request.video_id,
            languages=request.languages
        )
        
        if metadata.get("error"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=metadata["error"]
            )
        
        chunks = youtube_service.create_semantic_chunks(segments)
        
        # Find the chunk containing current timestamp
        current_chunk = youtube_service.find_chunk_at_timestamp(
            chunks,
            request.current_timestamp
        )
        
        if not current_chunk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No content found for timestamp {request.current_timestamp:.1f}s"
            )
        
        # Generate AI summary if requested
        ai_summary = None
        key_concepts = []
        key_points = []
        
        if request.generate_full_chunk:
            # Use the transformer to generate educational summary
            transform_request = TransformationRequest(
                content_id=f"youtube_{metadata['video_id']}",
                start_time=current_chunk.start_time,
                end_time=current_chunk.end_time,
                target_size_kb=64,
                include_images=False,
                priority="high",
                user_bandwidth_kbps=0,  # Simulating network drop
                previous_position=request.current_timestamp,
                transcript_hint=current_chunk.text
            )
            
            result = await transformer.transform_content(transform_request)
            ai_summary = result.summary.text
            key_concepts = result.summary.key_concepts
            key_points = result.summary.key_points
        
        # Get adjacent chunks for context
        prev_chunk = None
        next_chunk = None
        
        if current_chunk.chunk_id > 0:
            prev = chunks[current_chunk.chunk_id - 1]
            prev_chunk = SemanticChunkResponse(
                chunk_id=prev.chunk_id,
                start_time=prev.start_time,
                end_time=prev.end_time,
                duration=prev.duration,
                text=prev.text[:200] + "...",  # Truncated preview
                segment_count=len(prev.segments)
            )
        
        if current_chunk.chunk_id < len(chunks) - 1:
            nxt = chunks[current_chunk.chunk_id + 1]
            next_chunk = SemanticChunkResponse(
                chunk_id=nxt.chunk_id,
                start_time=nxt.start_time,
                end_time=nxt.end_time,
                duration=nxt.duration,
                text=nxt.text[:200] + "...",  # Truncated preview
                segment_count=len(nxt.segments)
            )
        
        current_response = SemanticChunkResponse(
            chunk_id=current_chunk.chunk_id,
            start_time=current_chunk.start_time,
            end_time=current_chunk.end_time,
            duration=current_chunk.duration,
            text=current_chunk.text,
            segment_count=len(current_chunk.segments),
            ai_summary=ai_summary,
            key_concepts=key_concepts,
            key_points=key_points
        )
        
        return ContinueLearningResponse(
            video_id=metadata["video_id"],
            current_timestamp=request.current_timestamp,
            relevant_chunk=current_response,
            previous_chunk=prev_chunk,
            next_chunk=next_chunk,
            message=f"Network dropped at {request.current_timestamp:.1f}s. Here's your learning summary to continue without video!"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate continue learning summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )
