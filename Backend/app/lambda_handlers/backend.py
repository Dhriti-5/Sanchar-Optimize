"""
Lambda Handler for FastAPI Backend
Wraps Sanchar-Optimize FastAPI application for AWS Lambda execution
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Lazy-load ASGI app and Mangum adapter
_asgi_app = None


def get_asgi_app():
    """Lazy-load ASGI app with Mangum adapter"""
    global _asgi_app
    if _asgi_app is None:
        try:
            # Import mangum only when needed (for Lambda runtime)
            from mangum import Mangum
        except ImportError:
            logger.warning("Mangum not installed; installing dynamically...")
            import subprocess
            subprocess.check_call(["pip", "install", "--quiet", "mangum==0.17.0"])
            from mangum import Mangum
        
        # Import FastAPI app
        try:
            from main import app as fastapi_app
        except ImportError:
            from app.main import app as fastapi_app
        
        # Wrap with Mangum adapter
        _asgi_app = Mangum(fastapi_app, lifespan="off")
    
    return _asgi_app


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for FastAPI application.
    
    Converts API Gateway Lambda Proxy integration events to ASGI format,
    processes through FastAPI, and returns API Gateway Lambda Proxy response.
    
    Event structure (API Gateway Lambda Proxy):
    {
        "resource": "/path",
        "requestContext": { "http": {"method": "GET"}, ... },
        "headers": { ... },
        "body": "...",
        "queryStringParameters": { ... },
        ...
    }
    
    Returns Lambda Proxy response:
    {
        "statusCode": 200,
        "headers": { "Content-Type": "application/json" },
        "body": "{...}",
        "isBase64Encoded": false
    }
    """
    try:
        asgi = get_asgi_app()
        return asgi(event, context)
    except Exception as e:
        logger.error(f"Error in backend handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error", "details": str(e)}),
            "isBase64Encoded": False
        }
