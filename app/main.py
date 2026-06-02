"""
FastAPI application factory for the Store Intelligence API.

Lifespan manages DB init/close.
Middleware: structured logging + global error handling.
Routers: health, events, metrics, funnel, heatmap, anomalies.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db, close_db
from app.db.init_db import seed_store, seed_pos_transactions
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.errors import register_error_handlers
from app.routers import events, metrics, funnel, heatmap, anomalies, health, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + seed. Shutdown: close DB."""
    await init_db()

    # Seed data on startup
    from app.db.session import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        await seed_store(session)
        await seed_pos_transactions(session)

    yield
    await close_db()


app = FastAPI(
    title="Store Intelligence API",
    description="Real-time retail analytics for Purplle brick-and-mortar stores",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured logging
app.add_middleware(RequestLoggingMiddleware)

# Global error handlers (no raw stack traces)
register_error_handlers(app)

# Register routers
app.include_router(health.router)
app.include_router(events.router)
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)
app.include_router(websocket.router)
