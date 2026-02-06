"""
ClearQuote – Async SQLAlchemy engine + ORM models.
Matches the 4 tables: vehicle_cards, damage_detections, repairs, quotes.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, Numeric
)
from config import config

# ---------------------------------------------------------------------------
# Base and Models (can be defined immediately)
# ---------------------------------------------------------------------------
Base = declarative_base()


# ---------------------------------------------------------------------------
# Engine and Session (created lazily)
# ---------------------------------------------------------------------------
engine = None
async_session_factory = None


def initialize_database():
    """
    Initialize the database engine and session factory.
    Must be called after DB_URL is configured.
    """
    global engine, async_session_factory
    
    if not config.DB_URL:
        raise RuntimeError(
            "DB_URL is not configured. "
            "Please set it via POST /api/config/db-url endpoint."
        )
    
    # Convert sync URL to async (asyncpg)
    _ASYNC_URL = config.DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(_ASYNC_URL, echo=False, pool_pre_ping=True)
    async_session_factory = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )


def get_session_factory():
    """
    Get the async session factory, ensuring database is initialized.
    """
    if async_session_factory is None:
        initialize_database()
    return async_session_factory


def get_engine():
    """
    Get the database engine, ensuring it's initialized.
    """
    if engine is None:
        initialize_database()
    return engine


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------
async def test_connection():
    """
    Test database connectivity.
    """
    current_engine = get_engine()
    async with current_engine.connect() as conn:
        from sqlalchemy import text
        await conn.execute(text("SELECT 1"))


# ---------------------------------------------------------------------------
# ORM Models (mirrors the assignment schema exactly)
# ---------------------------------------------------------------------------

class VehicleCard(Base):
    __tablename__ = "vehicle_cards"

    card_id          = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_type     = Column(String(50))
    manufacturer     = Column(String(100))
    model            = Column(String(100))
    manufacture_year = Column(Integer)
    created_at       = Column(DateTime)


class DamageDetection(Base):
    __tablename__ = "damage_detections"

    damage_id  = Column(Integer, primary_key=True, autoincrement=True)
    card_id    = Column(Integer)                  # FK → vehicle_cards
    panel_name = Column(String(100))
    damage_type= Column(String(100))
    severity   = Column(String(50))               # low / medium / high / severe
    confidence = Column(Float)                    # 0–1 or 0–100
    detected_at= Column(DateTime)


class Repair(Base):
    __tablename__ = "repairs"

    repair_id    = Column(Integer, primary_key=True, autoincrement=True)
    card_id      = Column(Integer)                # FK → vehicle_cards
    panel_name   = Column(String(100))
    repair_action= Column(String(200))
    repair_cost  = Column(Numeric(12, 2))
    approved     = Column(Boolean)
    created_at   = Column(DateTime)


class Quote(Base):
    __tablename__ = "quotes"

    quote_id            = Column(Integer, primary_key=True, autoincrement=True)
    card_id             = Column(Integer)         # FK → vehicle_cards
    total_estimated_cost= Column(Numeric(12, 2))
    currency            = Column(String(10))
    generated_at        = Column(DateTime)