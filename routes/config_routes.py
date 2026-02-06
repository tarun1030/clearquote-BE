"""
ClearQuote – Configuration endpoints.

POST /api/config/api-key     – update the Gemini API key
POST /api/config/db-url      – update the PostgreSQL connection string
GET  /api/config/db-status   – verify current database connection
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from datetime import datetime
from config import config

router = APIRouter(prefix="/api/config", tags=["config"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class UpdateApiKeyRequest(BaseModel):
    """Request body for updating the API key."""
    api_key: str


class UpdateDbUrlRequest(BaseModel):
    """Request body for updating the database URL."""
    db_url: str


class ConfigResponse(BaseModel):
    """Response confirming the configuration update."""
    message: str
    status: str


# ---------------------------------------------------------------------------
# Helper Functions for Testing Connections
# ---------------------------------------------------------------------------
async def test_api_key_connection(api_key: str) -> dict:
    """
    Test if the provided Gemini API key is valid and can authenticate.
    
    Args:
        api_key: The Gemini API key to test
        
    Returns:
        Dictionary with status and details
    """
    try:
        if not api_key or not api_key.strip():
            return {
                "status": "invalid",
                "message": "API key is empty",
                "is_valid": False
            }
        
        # Configure genai with the test key
        genai.configure(api_key=api_key.strip())
        
        # Try to list available models to validate the key
        models = genai.list_models()
        models_list = list(models)
        
        if models_list:
            return {
                "status": "valid",
                "message": "Gemini API key is valid and authenticated",
                "is_valid": True,
                "available_models": len(models_list)
            }
        else:
            return {
                "status": "invalid",
                "message": "API key appears invalid - no models available",
                "is_valid": False
            }
            
    except ValueError as e:
        if "API key" in str(e):
            return {
                "status": "invalid",
                "message": f"Invalid API key: {str(e)}",
                "is_valid": False
            }
        return {
            "status": "invalid",
            "message": f"Authentication failed: {str(e)}",
            "is_valid": False
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error testing API key: {str(e)}",
            "is_valid": False
        }


async def test_database_connection(db_url: str) -> dict:
    """
    Test if a PostgreSQL connection string is valid and the database is accessible.
    Automatically URL-encodes password.
    """

    try:
        if not db_url or not db_url.strip():
            return {
                "status": "invalid",
                "message": "Database URL is empty",
                "is_connected": False
            }

        if not db_url.startswith("postgresql"):
            return {
                "status": "invalid",
                "message": "Invalid connection string format. Must start with 'postgresql'",
                "is_connected": False
            }

        # ---- NEW LOGIC (Password Encoding) ----
        from urllib.parse import urlparse, quote_plus

        parsed = urlparse(db_url)

        username = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port
        database = parsed.path.lstrip("/")

        if password:
            password = quote_plus(password)

        safe_sync_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"

        # Convert to async URL
        async_url = safe_sync_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1
        )

        # --------------------------------------

        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        test_engine = create_async_engine(async_url, echo=False)

        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        await test_engine.dispose()

        return {
            "status": "connected",
            "message": "PostgreSQL connection is healthy and database is accessible",
            "is_connected": True,
            "database_name": database,
            "connection_type": "postgresql"
        }

    except Exception as e:
        return {
            "status": "disconnected",
            "message": f"Failed to connect to database: {str(e)}",
            "is_connected": False,
            "error_type": type(e).__name__
        }



# ---------------------------------------------------------------------------
# POST /api/config/api-key – update the Gemini API key
# ---------------------------------------------------------------------------
@router.post("/api-key", response_model=ConfigResponse)
async def update_api_key(req: UpdateApiKeyRequest):
    """
    Updates the Gemini API key.
    Validates that the key is not empty and saves to JSON config.
    """
    if not req.api_key or not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    try:
        # Save to JSON config
        config.GEMINI_API_KEY = req.api_key.strip()
        
        return ConfigResponse(
            message=f"API key updated successfully and saved to configuration",
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")


# ---------------------------------------------------------------------------
# POST /api/config/db-url – update the PostgreSQL connection string
# ---------------------------------------------------------------------------
@router.post("/db-url", response_model=ConfigResponse)
async def update_db_url(req: UpdateDbUrlRequest):
    """
    Updates the PostgreSQL connection string (DB_URL).
    Saves to JSON config for persistence.
    """
    if not req.db_url or not req.db_url.strip():
        raise HTTPException(status_code=400, detail="DB URL cannot be empty")

    if not req.db_url.startswith("postgresql"):
        raise HTTPException(
            status_code=400,
            detail="DB URL must be a valid PostgreSQL connection string"
        )

    try:
        # Save to JSON config
        config.DB_URL = req.db_url.strip()
        
        return ConfigResponse(
            message="DB URL updated successfully and saved to configuration",
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB URL: {str(e)}")


# ---------------------------------------------------------------------------
# GET /api/config/status – verify current configuration
# ---------------------------------------------------------------------------
@router.get("/status", response_model=dict)
async def get_config_status():
    """
    Returns the current configuration status.
    Shows which configuration values are set.
    """
    return {
        "gemini_api_key_set": config.GEMINI_API_KEY is not None,
        "db_url_set": config.DB_URL is not None,
        "gemini_model": config.GEMINI_MODEL,
        "validation": config.validate_config()
    }


# ---------------------------------------------------------------------------
# GET /api/config/api-key-status – verify Gemini API key validity
# ---------------------------------------------------------------------------
@router.get("/api-key-status", response_model=dict)
async def get_api_key_status():
    """
    Returns the current Gemini API key status.
    Tests if the key is valid and can authenticate with Google Generative AI.
    """
    result = await test_api_key_connection(config.GEMINI_API_KEY)
    return result


# ---------------------------------------------------------------------------
# POST /api/config/test-connection – test both DB and API key
# ---------------------------------------------------------------------------
@router.post("/test-connection", response_model=dict)
async def test_all_connections():
    """
    Tests both database and API key connections.
    Returns a comprehensive status report for both services.
    """
    db_result = await test_database_connection(config.DB_URL)
    api_result = await test_api_key_connection(config.GEMINI_API_KEY)
    
    overall_status = "healthy" if (db_result.get("is_connected") and api_result.get("is_valid")) else "degraded"
    
    return {
        "overall_status": overall_status,
        "database": db_result,
        "gemini_api": api_result,
        "timestamp": str(datetime.now()), 
    }


# ---------------------------------------------------------------------------
# POST /api/config/validate-api-key – validate a new API key before saving
# ---------------------------------------------------------------------------
@router.post("/validate-api-key", response_model=dict)
async def validate_api_key(req: UpdateApiKeyRequest):
    """
    Validates a new API key without saving it.
    Useful for testing before actually updating the configuration.
    """
    result = await test_api_key_connection(req.api_key)
    return result


# ---------------------------------------------------------------------------
# POST /api/config/validate-db-url – validate a new DB URL before saving
# ---------------------------------------------------------------------------
@router.post("/validate-db-url", response_model=dict)
async def validate_db_url(req: UpdateDbUrlRequest):
    """
    Validates a new database URL without saving it.
    Useful for testing before actually updating the configuration.
    """
    result = await test_database_connection(req.db_url)
    return result