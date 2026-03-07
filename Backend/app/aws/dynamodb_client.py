"""
Amazon DynamoDB Client
Handles session memory and contextual tracking across modality transitions
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal
import json
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """Client for DynamoDB session memory operations"""
    
    def __init__(self):
        """Initialize DynamoDB client"""
        self.client = None
        self.resource = None
        # Use explicit table names from environment if provided, otherwise build from prefix
        self.table_name = settings.DYNAMODB_SESSIONS_TABLE or f"{settings.DYNAMODB_TABLE_PREFIX}_sessions"
        self.transitions_table_name = settings.DYNAMODB_TRANSITIONS_TABLE or f"{settings.DYNAMODB_TABLE_PREFIX}_transitions"
        self.available = False
        
        try:
            # Initialize client and resource
            # In Lambda, use IAM role credentials automatically (don't pass explicit credentials)
            import os
            is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
            
            session_kwargs = {
                'region_name': settings.AWS_REGION
            }
            
            # Only use explicit credentials if not in Lambda and they are set
            if not is_lambda and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                session_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                session_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
            
            self.client = boto3.client('dynamodb', **session_kwargs)
            self.resource = boto3.resource('dynamodb', **session_kwargs)
            
            self.available = True
            logger.info("DynamoDB client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB client: {e}")
            self.available = False
    
    def _serialize_for_dynamodb(self, obj: Any) -> Any:
        """Convert Python types to DynamoDB compatible types"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._serialize_for_dynamodb(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_dynamodb(v) for v in obj]
        return obj
    
    def _deserialize_from_dynamodb(self, obj: Any) -> Any:
        """Convert DynamoDB types back to Python types"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._deserialize_from_dynamodb(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deserialize_from_dynamodb(v) for v in obj]
        return obj
    
    async def create_session(
        self,
        session_id: str,
        user_agent: str,
        platform: str = "web"
    ) -> bool:
        """
        Create a new user session
        
        Args:
            session_id: Unique session identifier
            user_agent: Browser user agent string
            platform: Platform type (web, mobile)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.available:
            logger.error(f"DynamoDB client not available - cannot create session {session_id}")
            return False
        
        try:
            table = self.resource.Table(self.table_name)
            
            now = datetime.now()
            timestamp = int(now.timestamp())  # Unix timestamp as number
            ttl = int((now + timedelta(days=7)).timestamp())  # 7-day persistence
            
            item = {
                'session_id': session_id,
                'created_at': timestamp,  # Number type to match DynamoDB schema
                'last_updated': timestamp,
                'user_agent': user_agent,
                'platform': platform,
                'current_modality': 'video',
                'content_progress': {},
                'transition_count': 0,
                'ttl': ttl
            }
            
            table.put_item(Item=item)
            logger.info(f"✓ Created session in DynamoDB: {session_id}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"✗ DynamoDB ClientError creating session {session_id}: {error_code} - {error_msg}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error creating session {session_id}: {type(e).__name__} - {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data or None
        """
        if not self.available:
            return None
        
        try:
            table = self.resource.Table(self.table_name)
            response = table.get_item(Key={'session_id': session_id})
            
            if 'Item' in response:
                return self._deserialize_from_dynamodb(response['Item'])
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None
    
    async def update_content_position(
        self,
        session_id: str,
        content_id: str,
        timestamp: float,
        modality: str,
        semantic_context: Optional[str] = None
    ) -> bool:
        """
        Update current position in content (Contextual Memory)
        
        Args:
            session_id: Session identifier
            content_id: Content identifier (video ID, URL, etc.)
            timestamp: Current timestamp in content (seconds)
            modality: Current modality (video, audio, text_summary)
            semantic_context: Optional semantic description of current position
            
        Returns:
            True if successful
        """
        if not self.available:
            return False
        
        try:
            table = self.resource.Table(self.table_name)
            
            timestamp_now = int(datetime.now().timestamp())
            progress_data = self._serialize_for_dynamodb({
                'timestamp': timestamp,
                'modality': modality,
                'last_updated': timestamp_now,
                'semantic_context': semantic_context or ''
            })
            
            table.update_item(
                Key={'session_id': session_id},
                UpdateExpression='SET content_progress.#cid = :progress, last_updated = :now, current_modality = :modality',
                ExpressionAttributeNames={
                    '#cid': content_id
                },
                ExpressionAttributeValues={
                    ':progress': progress_data,
                    ':now': timestamp_now,
                    ':modality': modality
                }
            )
            
            logger.debug(f"Updated content position for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating content position: {e}")
            return False
    
    async def get_content_position(
        self,
        session_id: str,
        content_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get last known position in content
        
        Args:
            session_id: Session identifier
            content_id: Content identifier
            
        Returns:
            Position data or None
        """
        if not self.available:
            return None
        
        try:
            session = await self.get_session(session_id)
            if session and 'content_progress' in session:
                progress = session['content_progress'].get(content_id)
                if progress:
                    return self._deserialize_from_dynamodb(progress)
            return None
            
        except Exception as e:
            logger.error(f"Error getting content position: {e}")
            return None
    
    async def record_modality_transition(
        self,
        session_id: str,
        content_id: str,
        from_modality: str,
        to_modality: str,
        timestamp: float,
        reason: str,
        network_conditions: Dict[str, Any]
    ) -> bool:
        """
        Record a modality transition event (Multi-Modal Handshake)
        
        Args:
            session_id: Session identifier
            content_id: Content identifier
            from_modality: Source modality
            to_modality: Target modality
            timestamp: Content timestamp when transition occurred
            reason: Reason for transition (predicted_drop, actual_drop, manual)
            network_conditions: Network metrics at time of transition
            
        Returns:
            True if successful
        """
        if not self.available:
            return False
        
        try:
            table = self.resource.Table(self.transitions_table_name)
            
            now = datetime.now()
            transition_timestamp = int(now.timestamp())  # Unix timestamp
            transition_id = f"{session_id}#{int(now.timestamp() * 1000)}"
            ttl = int((now + timedelta(days=30)).timestamp())  # 30-day retention
            
            item = self._serialize_for_dynamodb({
                'transition_id': transition_id,
                'session_id': session_id,
                'timestamp': transition_timestamp,
                'content_id': content_id,
                'from_modality': from_modality,
                'to_modality': to_modality,
                'content_timestamp': timestamp,
                'reason': reason,
                'network_conditions': network_conditions,
                'ttl': ttl
            })
            
            table.put_item(Item=item)
            
            # Increment transition count in session
            sessions_table = self.resource.Table(self.table_name)
            sessions_table.update_item(
                Key={'session_id': session_id},
                UpdateExpression='ADD transition_count :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            
            logger.info(f"Recorded transition: {from_modality} → {to_modality} for session {session_id}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.error(f"DynamoDB table not found: {self.transitions_table_name}")
            else:
                logger.error(f"Error recording transition: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error recording transition: {e}")
            return False
    
    async def get_transition_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get transition history for a session
        
        Args:
            session_id: Session identifier
            limit: Maximum number of transitions to return
            
        Returns:
            List of transition records
        """
        if not self.available:
            return []
        
        try:
            table = self.resource.Table(self.transitions_table_name)
            
            response = table.query(
                IndexName='session_id-transition_time-index',
                KeyConditionExpression='session_id = :sid',
                ExpressionAttributeValues={':sid': session_id},
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            
            transitions = [self._deserialize_from_dynamodb(item) for item in response.get('Items', [])]
            logger.debug(f"Retrieved {len(transitions)} transitions for session {session_id}")
            return transitions
            
        except ClientError as e:
            if 'ResourceNotFoundException' in str(e) or 'ValidationException' in str(e):
                logger.warning(f"Index not found, querying without index")
                # Fallback: scan with filter
                response = table.scan(
                    FilterExpression='session_id = :sid',
                    ExpressionAttributeValues={':sid': session_id},
                    Limit=limit
                )
                return [self._deserialize_from_dynamodb(item) for item in response.get('Items', [])]
            else:
                logger.error(f"Error getting transition history: {e}")
                return []
        except Exception as e:
            logger.error(f"Unexpected error getting transition history: {e}")
            return []
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (older than 7 days)
        Note: DynamoDB TTL handles this automatically, but this is for manual cleanup
        
        Returns:
            Number of sessions cleaned up
        """
        if not self.available:
            return 0
        
        try:
            table = self.resource.Table(self.table_name)
            cutoff_time = datetime.now() - timedelta(days=7)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            # Scan for expired sessions
            response = table.scan(
                FilterExpression='last_updated < :cutoff',
                ExpressionAttributeValues={':cutoff': cutoff_timestamp}
            )
            
            count = 0
            with table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={'session_id': item['session_id']})
                    count += 1
            
            logger.info(f"Cleaned up {count} expired sessions")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0


# Global instance
dynamodb_client = DynamoDBClient()
