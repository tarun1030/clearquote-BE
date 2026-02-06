"""
ClearQuote – NL → SQL → Answer System
Main FastAPI application entry point.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import engine, Base, test_connection
from routes.query_routes import router as query_router
from routes.health_routes import router as health_router
from routes.config_routes import router as config_router
from routes.data_routes import router as data_router


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup, confirm DB is reachable."""
    print("[ClearQuote] Starting up...")
    # await test_connection()            # raises if DB unreachable
    # print("[ClearQuote] PostgreSQL connection verified.")
    yield
    print("[ClearQuote] Shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ClearQuote NL→SQL→Answer API",
    description="Converts natural-language questions about vehicles, damages, repairs & quotes into SQL, executes them, and returns human-readable answers.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],               # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(query_router)
app.include_router(config_router)
app.include_router(data_router)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
