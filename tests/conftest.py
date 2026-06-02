"""
Shared test fixtures for the Store Intelligence API test suite.

Provides:
  - Async SQLite test database (isolated per test)
  - AsyncClient fixture via httpx
  - Sample event factories
"""

import os
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone

# Set test DB BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import init_db, close_db, get_session_factory
from app.models.db import Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize a fresh SQLite database for each test."""
    # Remove old test db
    if os.path.exists("test.db"):
        os.remove("test.db")

    await init_db()

    # Seed the store
    from app.db.init_db import seed_store
    factory = get_session_factory()
    async with factory() as session:
        await seed_store(session)

    yield

    await close_db()

    if os.path.exists("test.db"):
        try:
            os.remove("test.db")
        except PermissionError:
            pass  # File locked on Windows


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_event(
    visitor_id: str = "VIS_0001",
    event_type: str = "ENTRY",
    store_id: str = "STORE_BLR_002",
    is_staff: bool = False,
    zone_id: str = None,
    dwell_ms: int = 0,
    confidence: float = 0.92,
    timestamp: str = None,
) -> dict:
    """Factory for creating valid test events."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": {"session_seq": 1},
    }


def make_entry_exit_pair(
    visitor_id: str = "VIS_0001",
    entry_ts: str = None,
    exit_ts: str = None,
) -> list:
    """Create an ENTRY + EXIT event pair for a visitor."""
    if entry_ts is None:
        entry_ts = "2026-04-10T14:00:00Z"
    if exit_ts is None:
        exit_ts = "2026-04-10T14:30:00Z"

    return [
        make_event(visitor_id=visitor_id, event_type="ENTRY", timestamp=entry_ts),
        make_event(visitor_id=visitor_id, event_type="EXIT", timestamp=exit_ts),
    ]
