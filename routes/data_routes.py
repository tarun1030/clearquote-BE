"""
ClearQuote – Data retrieval endpoints.

POST /api/data/fetch – get all data from specified table(s)
Supported tables: damage_detections, repairs, quotes, vehicle_cards
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from config import config

router = APIRouter(prefix="/api/data", tags=["data"])


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class FetchDataRequest(BaseModel):
    """Request body for fetching data from table(s)."""
    tables: List[str] = ["vehicle_cards", "damage_detections", "repairs", "quotes"]
    limit: int = 1000  # Limit rows per table to prevent massive responses


class FetchDataResponse(BaseModel):
    """Response containing data from requested tables."""
    status: str
    message: str
    data: Dict[str, List[Dict[str, Any]]]
    row_counts: Dict[str, int]


# Allowed tables
ALLOWED_TABLES = {
    "vehicle_cards",
    "damage_detections",
    "repairs",
    "quotes"
}


# ---------------------------------------------------------------------------
# Database Session Factory
# ---------------------------------------------------------------------------
def get_async_engine():
    """
    Creates an async database engine using the current DB_URL from config.
    This ensures we always use the latest configuration.
    """
    db_url = config.DB_URL
    
    if not db_url:
        raise HTTPException(
            status_code=500,
            detail="Database URL is not configured. Please configure it via /api/config/db-url"
        )
    
    # Convert postgresql:// to postgresql+asyncpg://
    if db_url.startswith("postgresql://"):
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql+asyncpg://"):
        async_url = db_url
    else:
        raise HTTPException(
            status_code=500,
            detail="Invalid database URL format. Must be a PostgreSQL connection string."
        )
    
    return create_async_engine(async_url, echo=False, pool_pre_ping=True)


@asynccontextmanager
async def get_async_session():
    """
    Context manager for async database sessions.
    Creates a new session using the current configuration.
    """
    engine = get_async_engine()
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await engine.dispose()


# ---------------------------------------------------------------------------
# POST /api/data/fetch – get all data from specified tables
# ---------------------------------------------------------------------------
@router.post("/fetch", response_model=FetchDataResponse)
async def fetch_data(req: FetchDataRequest):
    """
    Fetches all data from the specified table(s).
    
    Supported tables:
    - vehicle_cards
    - damage_detections
    - repairs
    - quotes
    
    Returns all rows from the specified tables, limited by the 'limit' parameter.
    """
    # Validate table names
    requested_tables = set(req.tables)
    invalid_tables = requested_tables - ALLOWED_TABLES
    
    if invalid_tables:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table names: {', '.join(invalid_tables)}. "
                   f"Allowed tables: {', '.join(ALLOWED_TABLES)}"
        )
    
    if not requested_tables:
        raise HTTPException(
            status_code=400,
            detail="No tables specified. Provide at least one table name."
        )
    
    if req.limit <= 0:
        raise HTTPException(
            status_code=400,
            detail="Limit must be greater than 0"
        )

    result_data = {}
    row_counts = {}

    try:
        async with get_async_session() as session:
            for table_name in requested_tables:
                try:
                    # Fetch data from the table
                    query = text(f"SELECT * FROM {table_name} LIMIT :limit")
                    result = await session.execute(query, {"limit": req.limit})
                    rows = result.fetchall()
                    
                    # Convert Row objects to dictionaries
                    row_dicts = [dict(row._mapping) for row in rows]
                    
                    result_data[table_name] = row_dicts
                    row_counts[table_name] = len(row_dicts)
                    
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error fetching data from table '{table_name}': {str(e)}"
                    )
        
        return FetchDataResponse(
            status="success",
            message=f"Successfully fetched data from {len(requested_tables)} table(s)",
            data=result_data,
            row_counts=row_counts
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )