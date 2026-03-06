"""
YouTube Transcript Service
Extracts video transcripts with timestamps for semantic chunking
Supports "continue learning" feature during network drops
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable
    )
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_AVAILABLE = False
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception
    VideoUnavailable = Exception

logger = logging.getLogger(__name__)


class TranscriptSegment:
    """Represents a segment of video transcript with timing"""
    
    def __init__(
        self,
        text: str,
        start: float,
        duration: float,
        segment_id: int
    ):
        self.text = text.strip()
        self.start = start
        self.end = start + duration
        self.duration = duration
        self.segment_id = segment_id
    
    def __repr__(self):
        return f"TranscriptSegment({self.start:.1f}s-{self.end:.1f}s, {len(self.text)} chars)"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "segment_id": self.segment_id
        }


class SemanticChunk:
    """Represents a semantically meaningful chunk of learning content"""
    
    def __init__(
        self,
        segments: List[TranscriptSegment],
        chunk_id: int,
        start_time: float,
        end_time: float
    ):
        self.segments = segments
        self.chunk_id = chunk_id
        self.start_time = start_time
        self.end_time = end_time
        self.duration = end_time - start_time
        self.text = " ".join(seg.text for seg in segments)
    
    def __repr__(self):
        return f"SemanticChunk({self.start_time:.1f}s-{self.end_time:.1f}s, {len(self.segments)} segments)"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "text": self.text,
            "segment_count": len(self.segments),
            "segments": [seg.to_dict() for seg in self.segments]
        }


class YouTubeTranscriptService:
    """
    Service for extracting and processing YouTube transcripts
    
    Features:
    - Extract full transcripts with timestamps
    - Semantic chunking (2-3 minute learning blocks)
    - Find relevant chunk for any timestamp (for network drop recovery)
    - Support for multiple languages
    """
    
    def __init__(self):
        """Initialize YouTube transcript service"""
        if not YOUTUBE_TRANSCRIPT_AVAILABLE:
            logger.warning("youtube-transcript-api not installed. Transcript extraction unavailable.")
            self.available = False
        else:
            self.available = True
            logger.info("YouTube Transcript Service initialized")
        
        # Chunking parameters
        self.target_chunk_duration = 150.0  # 2.5 minutes per chunk
        self.min_chunk_duration = 90.0      # Minimum 1.5 minutes
        self.max_chunk_duration = 210.0     # Maximum 3.5 minutes
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from various URL formats
        
        Args:
            url: YouTube URL or video ID
            
        Returns:
            Video ID or None if not found
        """
        # If it's already just the ID (11 characters, alphanumeric + - and _)
        if re.match(r'^[A-Za-z0-9_-]{11}$', url):
            return url
        
        # Match various YouTube URL patterns
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]{11})',
            r'youtube\.com\/embed\/([A-Za-z0-9_-]{11})',
            r'youtube\.com\/v\/([A-Za-z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def get_transcript(
        self,
        video_id: str,
        languages: Optional[List[str]] = None
    ) -> Tuple[List[TranscriptSegment], Dict[str, Any]]:
        """
        Get full transcript with timestamps for a YouTube video
        
        Args:
            video_id: YouTube video ID
            languages: Preferred language codes (e.g., ['en', 'hi', 'auto'])
            
        Returns:
            Tuple of (list of transcript segments, metadata dict)
        """
        if not self.available:
            logger.error("YouTube transcript service not available")
            return [], {"error": "Service not available"}
        
        # Extract video ID from URL if needed
        video_id = self.extract_video_id(video_id) or video_id
        
        # Default to English if no language specified
        if languages is None:
            languages = ['en']
        
        try:
            logger.info(f"Fetching transcript for video: {video_id}")
            
            # Fetch transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=languages
            )
            
            # Convert to TranscriptSegment objects
            segments = []
            for idx, entry in enumerate(transcript_list):
                segment = TranscriptSegment(
                    text=entry['text'],
                    start=entry['start'],
                    duration=entry['duration'],
                    segment_id=idx
                )
                segments.append(segment)
            
            metadata = {
                "video_id": video_id,
                "segment_count": len(segments),
                "total_duration": segments[-1].end if segments else 0.0,
                "language": languages[0] if languages else "en",
                "fetched_at": datetime.now().isoformat()
            }
            
            logger.info(f"Transcript extracted: {len(segments)} segments, "
                       f"{metadata['total_duration']:.1f}s duration")
            
            return segments, metadata
            
        except TranscriptsDisabled:
            logger.error(f"Transcripts disabled for video: {video_id}")
            return [], {"error": "Transcripts disabled for this video"}
        
        except NoTranscriptFound:
            logger.error(f"No transcript found for video: {video_id} in languages: {languages}")
            return [], {"error": f"No transcript found in languages: {languages}"}
        
        except VideoUnavailable:
            logger.error(f"Video unavailable: {video_id}")
            return [], {"error": "Video unavailable"}
        
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            return [], {"error": str(e)}
    
    def create_semantic_chunks(
        self,
        segments: List[TranscriptSegment]
    ) -> List[SemanticChunk]:
        """
        Divide transcript into semantic learning blocks
        
        Creates chunks of approximately 2-3 minutes, attempting to break
        at natural boundaries (sentence endings, pauses, topic shifts)
        
        Args:
            segments: List of transcript segments
            
        Returns:
            List of semantic chunks
        """
        if not segments:
            return []
        
        chunks = []
        current_segments = []
        chunk_start_time = segments[0].start
        chunk_id = 0
        
        for segment in segments:
            current_segments.append(segment)
            current_duration = segment.end - chunk_start_time
            
            # Check if we should create a chunk
            should_chunk = False
            
            # Must chunk if we exceed max duration
            if current_duration >= self.max_chunk_duration:
                should_chunk = True
            
            # Prefer to chunk at natural boundaries when near target duration
            elif current_duration >= self.target_chunk_duration:
                # Check if this looks like a good breaking point
                text = segment.text.lower()
                is_sentence_end = text.endswith(('.', '!', '?'))
                is_topic_marker = any(marker in text for marker in [
                    'now', 'next', 'so', 'therefore', 'in conclusion',
                    'let\'s move on', 'moving on', 'another', 'finally'
                ])
                
                if is_sentence_end or is_topic_marker:
                    should_chunk = True
            
            if should_chunk and current_duration >= self.min_chunk_duration:
                # Create chunk
                chunk = SemanticChunk(
                    segments=current_segments,
                    chunk_id=chunk_id,
                    start_time=chunk_start_time,
                    end_time=segment.end
                )
                chunks.append(chunk)
                
                # Reset for next chunk
                current_segments = []
                chunk_start_time = segment.end
                chunk_id += 1
        
        # Add remaining segments as final chunk
        if current_segments:
            chunk = SemanticChunk(
                segments=current_segments,
                chunk_id=chunk_id,
                start_time=chunk_start_time,
                end_time=current_segments[-1].end
            )
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} semantic chunks from {len(segments)} segments")
        
        return chunks
    
    def find_chunk_at_timestamp(
        self,
        chunks: List[SemanticChunk],
        timestamp: float
    ) -> Optional[SemanticChunk]:
        """
        Find the semantic chunk containing a specific timestamp
        
        Used for "continue learning" feature during network drops
        
        Args:
            chunks: List of semantic chunks
            timestamp: Video timestamp in seconds
            
        Returns:
            The chunk containing the timestamp, or None
        """
        for chunk in chunks:
            if chunk.start_time <= timestamp <= chunk.end_time:
                return chunk
        
        # If exact match not found, return closest chunk
        if chunks:
            closest = min(chunks, key=lambda c: abs(c.start_time - timestamp))
            logger.info(f"Exact match not found for {timestamp:.1f}s, "
                       f"returning closest chunk at {closest.start_time:.1f}s")
            return closest
        
        return None
    
    def extract_segment_text(
        self,
        segments: List[TranscriptSegment],
        start_time: float,
        end_time: float
    ) -> str:
        """
        Extract transcript text for a specific time range
        
        Args:
            segments: List of transcript segments
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            Concatenated transcript text for the time range
        """
        relevant_segments = [
            seg for seg in segments
            if seg.start >= start_time and seg.end <= end_time
        ]
        
        if not relevant_segments:
            # Find overlapping segments
            relevant_segments = [
                seg for seg in segments
                if (seg.start <= end_time and seg.end >= start_time)
            ]
        
        return " ".join(seg.text for seg in relevant_segments)
