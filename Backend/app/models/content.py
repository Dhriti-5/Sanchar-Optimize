"""
Content Models
Represents video content and transformation data
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class ContentSegment(BaseModel):
    """A segment of content with associated metadata"""
    
    segment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str
    start_time: float = Field(..., ge=0.0, description="Segment start time (seconds)")
    end_time: float = Field(..., gt=0.0, description="Segment end time (seconds)")
    
    # Content data
    transcript: Optional[str] = Field(None, description="Transcript text")
    has_visual_elements: bool = Field(default=False)
    visual_description: Optional[str] = Field(None, description="Description of visual elements")
    
    # Educational metadata
    key_concepts: List[str] = Field(default_factory=list)
    learning_objectives: List[str] = Field(default_factory=list)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Educational importance")
    
    class Config:
        json_schema_extra = {
            "example": {
                "segment_id": "seg_abc123",
                "content_id": "video_edu_123",
                "start_time": 120.0,
                "end_time": 180.0,
                "transcript": "Let's discuss the concept of derivatives...",
                "has_visual_elements": True,
                "visual_description": "Graph showing tangent line to curve",
                "key_concepts": ["derivative", "tangent line", "slope"],
                "learning_objectives": ["Understand derivative concept"],
                "importance_score": 0.9
            }
        }


class Summary(BaseModel):
    """AI-generated content summary"""
    
    summary_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str
    segment_id: Optional[str] = None
    
    # Summary content
    text: str = Field(..., description="Summary text")
    key_concepts: List[str] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)
    
    # Visual elements
    images: List[str] = Field(default_factory=list, description="URLs to generated concept images")
    diagrams: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Metadata
    original_duration_seconds: float
    compression_ratio: float = Field(..., description="Summary size / original size")
    semantic_coverage_score: float = Field(default=0.0, ge=0.0, le=1.0, description="How well it covers original")
    
    generation_timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    model_version: str = Field(default="bedrock-claude-3.5-sonnet")
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary_id": "sum_abc123",
                "content_id": "video_edu_123",
                "segment_id": "seg_abc123",
                "text": "Derivatives represent the rate of change...",
                "key_concepts": ["derivative", "rate of change"],
                "key_points": [
                    "Derivative is slope of tangent line",
                    "Measures instantaneous rate of change"
                ],
                "images": ["https://s3.../derivative_graph.png"],
                "diagrams": [],
                "original_duration_seconds": 60.0,
                "compression_ratio": 0.08,
                "semantic_coverage_score": 0.92,
                "generation_timestamp": 1709251200.0,
                "model_version": "bedrock-claude-3.5-sonnet"
            }
        }


class TransformationRequest(BaseModel):
    """Request to transform content to summary"""
    
    content_id: str
    start_time: float
    end_time: float
    
    # Generation options
    target_size_kb: Optional[int] = Field(None, description="Target summary size")
    include_images: bool = Field(default=False, description="Generate concept images")
    priority: str = Field(default="normal", description="Processing priority")
    
    # Context
    user_bandwidth_kbps: float = Field(..., description="User's current bandwidth")
    previous_position: Optional[float] = Field(None, description="Where user left off")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "video_edu_123",
                "start_time": 120.0,
                "end_time": 180.0,
                "target_size_kb": 50,
                "include_images": False,
                "priority": "high",
                "user_bandwidth_kbps": 300.0,
                "previous_position": 120.5
            }
        }


class TransformationResponse(BaseModel):
    """Response with transformed content"""
    
    transformation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    summary: Summary
    
    # Delivery info
    content_url: Optional[str] = Field(None, description="URL to fetch full summary")
    estimated_size_kb: float
    
    # Performance
    generation_time_ms: int
    cache_hit: bool = Field(default=False)
    
    class Config:
        json_schema_extra = {
            "example": {
                "transformation_id": "trans_abc123",
                "summary": {},  # Summary object
                "content_url": "https://s3.../summaries/sum_abc123.json",
                "estimated_size_kb": 45.2,
                "generation_time_ms": 2500,
                "cache_hit": False
            }
        }


class TranscriptCache(BaseModel):
    """Cached transcript data"""
    
    content_id: str
    transcript: str
    timestamps: List[Dict[str, float]] = Field(default_factory=list, description="Word timestamps")
    
    cache_timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    ttl_seconds: int = Field(default=3600)
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "video_edu_123",
                "transcript": "Full video transcript...",
                "timestamps": [
                    {"word": "Hello", "start": 0.0, "end": 0.5}
                ],
                "cache_timestamp": 1709251200.0,
                "ttl_seconds": 3600
            }
        }
