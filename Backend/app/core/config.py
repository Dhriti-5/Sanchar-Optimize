"""
Core Application Configuration
Uses Pydantic Settings for environment variable management
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "chrome-extension://*"
    ]
    
    # AWS Configuration
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    
    # Amazon Bedrock
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    BEDROCK_MAX_TOKENS: int = 4096
    BEDROCK_TEMPERATURE: float = 0.7
    
    # Database
    TIMESTREAM_DATABASE: str = "sanchar_optimize"
    TIMESTREAM_TABLE: str = "network_telemetry"
    DYNAMODB_TABLE_PREFIX: str = "sanchar_optimize"
    REDIS_URL: str = "redis://localhost:6379"
    
    # S3 Storage
    S3_BUCKET_NAME: str = "sanchar-optimize-content"
    S3_CACHE_PREFIX: str = "cache/"
    
    # Network Sentry Configuration
    PREDICTION_THRESHOLD: float = 0.75
    HIGH_SPEED_THRESHOLD_KMH: float = 60.0
    MONITORING_FREQUENCY_HZ: int = 1
    HIGH_SPEED_MONITORING_FREQUENCY_HZ: int = 4
    
    # Modality Thresholds (Kbps)
    VIDEO_MIN_BANDWIDTH: int = 1000
    AUDIO_MIN_BANDWIDTH: int = 500
    
    # Content Transformation
    MAX_SUMMARY_SIZE_RATIO: float = 0.10
    TRANSCRIPT_CACHE_TTL_SECONDS: int = 3600
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
