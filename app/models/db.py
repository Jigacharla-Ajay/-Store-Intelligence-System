"""
SQLAlchemy ORM models for the Store Intelligence System.

Tables (in dependency order):
  1. stores         — Physical store reference data
  2. events         — Immutable append-only event log (source of truth)
  3. sessions       — Derived visitor sessions from ENTRY/EXIT pairs
  4. zone_visits    — Individual zone visit records linked to sessions
  5. pos_transactions — POS transaction records for conversion computation
  6. anomaly_log    — Persistent anomaly detection log

Schema follows database_schema.md exactly.
"""

import uuid
from datetime import datetime, timezone, time

from sqlalchemy import (
    Column, String, Boolean, Integer, SmallInteger, Float,
    DateTime, Time, Text, ForeignKey, CheckConstraint, Index,
    JSON, Numeric, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _utcnow():
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def _new_uuid():
    """Generate a new UUID v4."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# 1. stores
# ---------------------------------------------------------------------------

class Store(Base):
    __tablename__ = "stores"

    store_id = Column(String(20), primary_key=True)
    store_name = Column(String(100), nullable=False)
    city = Column(String(50), nullable=False)
    open_time = Column(Time, nullable=False, default=time(10, 0))
    close_time = Column(Time, nullable=False, default=time(22, 0))
    timezone = Column(String(50), nullable=False, default="Asia/Kolkata")
    layout_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    events = relationship("Event", back_populates="store", lazy="dynamic")
    sessions = relationship("Session", back_populates="store", lazy="dynamic")
    pos_transactions = relationship("PosTransaction", back_populates="store", lazy="dynamic")
    anomalies = relationship("AnomalyLog", back_populates="store", lazy="dynamic")

    __table_args__ = (
        Index("idx_stores_city", "city"),
    )


# ---------------------------------------------------------------------------
# 2. events
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = (
    "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
    "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY",
)


class Event(Base):
    __tablename__ = "events"

    event_id = Column(String(36), primary_key=True)  # UUID v4 as string
    store_id = Column(String(20), ForeignKey("stores.store_id"), nullable=False)
    camera_id = Column(String(50), nullable=False)
    visitor_id = Column(String(20), nullable=False)
    event_type = Column(String(30), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    zone_id = Column(String(50), nullable=True)
    dwell_ms = Column(Integer, nullable=False, default=0)
    is_staff = Column(Boolean, nullable=False, default=False)
    confidence = Column(Numeric(4, 3), nullable=False)
    event_metadata = Column("metadata", JSON, nullable=False, default=dict)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    store = relationship("Store", back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('ENTRY','EXIT','ZONE_ENTER','ZONE_EXIT','ZONE_DWELL',"
            "'BILLING_QUEUE_JOIN','BILLING_QUEUE_ABANDON','REENTRY')",
            name="chk_event_type",
        ),
        CheckConstraint("dwell_ms >= 0", name="chk_dwell_ms"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="chk_confidence_range",
        ),
        Index("idx_events_store_time", "store_id", "timestamp"),
        Index("idx_events_visitor", "visitor_id", "timestamp"),
        Index("idx_events_type_store", "event_type", "store_id"),
        Index("idx_events_staff", "is_staff", "store_id"),
    )


# ---------------------------------------------------------------------------
# 3. sessions
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(_new_uuid()))
    visitor_id = Column(String(20), nullable=False)
    store_id = Column(String(20), ForeignKey("stores.store_id"), nullable=False)
    entry_at = Column(DateTime(timezone=True), nullable=False)
    exit_at = Column(DateTime(timezone=True), nullable=True)  # NULL if still open
    is_converted = Column(Boolean, nullable=False, default=False)
    reentry_count = Column(SmallInteger, nullable=False, default=0)
    session_seq = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    store = relationship("Store", back_populates="sessions")
    zone_visits = relationship("ZoneVisit", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_store_entry", "store_id", "entry_at"),
        Index("idx_sessions_visitor", "visitor_id", "store_id"),
        Index("idx_sessions_converted", "store_id", "is_converted", "entry_at"),
    )


# ---------------------------------------------------------------------------
# 4. zone_visits
# ---------------------------------------------------------------------------

class ZoneVisit(Base):
    __tablename__ = "zone_visits"

    zone_visit_id = Column(String(36), primary_key=True, default=lambda: str(_new_uuid()))
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    store_id = Column(String(20), ForeignKey("stores.store_id"), nullable=False)
    zone_id = Column(String(50), nullable=False)
    enter_at = Column(DateTime(timezone=True), nullable=False)
    exit_at = Column(DateTime(timezone=True), nullable=True)  # NULL if still in zone
    dwell_ms = Column(Integer, nullable=True)  # Computed on zone exit
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    session = relationship("Session", back_populates="zone_visits")

    __table_args__ = (
        Index("idx_zone_visits_session", "session_id"),
        Index("idx_zone_visits_store_zone", "store_id", "zone_id", "enter_at"),
    )


# ---------------------------------------------------------------------------
# 5. pos_transactions
# ---------------------------------------------------------------------------

class PosTransaction(Base):
    __tablename__ = "pos_transactions"

    transaction_id = Column(String(30), primary_key=True)
    store_id = Column(String(20), ForeignKey("stores.store_id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    basket_value_inr = Column(Numeric(10, 2), nullable=False)
    correlated_session = Column(String(36), ForeignKey("sessions.session_id"), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    store = relationship("Store", back_populates="pos_transactions")

    __table_args__ = (
        CheckConstraint("basket_value_inr >= 0", name="chk_basket_value"),
        Index("idx_pos_store_time", "store_id", "timestamp"),
    )


# ---------------------------------------------------------------------------
# 6. anomaly_log
# ---------------------------------------------------------------------------

class AnomalyLog(Base):
    __tablename__ = "anomaly_log"

    anomaly_id = Column(String(36), primary_key=True, default=lambda: str(_new_uuid()))
    store_id = Column(String(20), ForeignKey("stores.store_id"), nullable=False)
    anomaly_type = Column(String(40), nullable=False)
    severity = Column(String(10), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    anomaly_metadata = Column("metadata", JSON, nullable=False, default=dict)
    suggested_action = Column(Text, nullable=True)

    # Relationships
    store = relationship("Store", back_populates="anomalies")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('INFO', 'WARN', 'CRITICAL')",
            name="chk_severity",
        ),
        Index("idx_anomaly_store_active", "store_id", "resolved_at"),
        Index("idx_anomaly_type", "anomaly_type", "store_id"),
    )
