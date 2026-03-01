"""
Sanchar-Optimize Backend - Phase 2
FastAPI application for Agentic Content Resiliency System
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api import telemetry, modality, health
from app.core.config import settings
from app.core.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    from pathlib import Path
    import os
    
    logger.info(">>> Sanchar-Optimize Backend starting...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"AWS Region: {settings.AWS_REGION}")
    logger.info(f"Working Directory: {Path.cwd()}")
    logger.info(f"Python Path: {os.getcwd()}")
    
    # Pre-load LSTM model to verify it loads
    logger.info("Pre-loading LSTM model...")
    from app.ml.model_loader import ModelLoader
    predictor = ModelLoader.load_lstm_predictor()
    if predictor.model is not None:
        logger.info(">>> LSTM MODEL LOADED SUCCESSFULLY AT STARTUP <<<")
    else:
        logger.warning(">>> LSTM MODEL NOT LOADED - USING HEURISTIC FALLBACK <<<")
    
    yield
    
    # Cleanup
    logger.info("<<< Sanchar-Optimize Backend shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Sanchar-Optimize API",
    description="Agentic Content Resiliency System for Rural India's Educational Access",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(telemetry.router, prefix="/api/v1", tags=["telemetry"])
app.include_router(modality.router, prefix="/api/v1", tags=["modality"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Sanchar-Optimize",
        "version": "2.0.0",
        "status": "operational",
        "phase": "2",
        "description": "Agentic Content Resiliency System"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )
