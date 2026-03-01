"""
AWS S3 Client
Handles S3 storage operations for content caching
"""

import logging
from typing import Optional, BinaryIO, Dict, Any
import json

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    """Client for AWS S3 operations"""
    
    def __init__(self):
        """Initialize S3 client"""
        if boto3 is None:
            logger.warning("boto3 not installed. S3 operations will be mocked.")
            self.client = None
            self.bucket_name = None
        else:
            try:
                self.client = boto3.client(
                    's3',
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
                )
                self.bucket_name = settings.S3_BUCKET_NAME
                logger.info(f"S3 client initialized for bucket {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                self.client = None
                self.bucket_name = None
    
    async def upload_summary(self, summary_id: str, summary_data: Dict[str, Any]) -> Optional[str]:
        """
        Upload summary to S3
        
        Args:
            summary_id: Summary identifier
            summary_data: Summary data dictionary
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if self.client is None:
            logger.warning("S3 client not available. Skipping upload.")
            return None
        
        try:
            key = f"{settings.S3_CACHE_PREFIX}summaries/{summary_id}.json"
            
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(summary_data),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Summary uploaded to {url}")
            
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload summary: {e}")
            return None
    
    async def get_summary(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve summary from S3
        
        Args:
            summary_id: Summary identifier
            
        Returns:
            Summary data if found, None otherwise
        """
        if self.client is None:
            return None
        
        try:
            key = f"{settings.S3_CACHE_PREFIX}summaries/{summary_id}.json"
            
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            data = json.loads(response['Body'].read())
            logger.debug(f"Summary retrieved from S3: {summary_id}")
            
            return data
            
        except ClientError as e:
            logger.debug(f"Summary not found in S3: {e}")
            return None
    
    async def upload_transcript(self, content_id: str, transcript: str) -> Optional[str]:
        """
        Upload transcript to S3
        
        Args:
            content_id: Content identifier
            transcript: Transcript text
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if self.client is None:
            return None
        
        try:
            key = f"{settings.S3_CACHE_PREFIX}transcripts/{content_id}.txt"
            
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=transcript,
                ContentType='text/plain',
                ServerSideEncryption='AES256'
            )
            
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Transcript uploaded to {url}")
            
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload transcript: {e}")
            return None
