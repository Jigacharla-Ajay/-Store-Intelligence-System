"""
Pydantic v2 models for event ingestion.

Covers:
  - EventMetadata: queue_depth, sku_zone, session_seq
  - EventModel: full event schema with UUID v4, event_type enum, confidence 0-1
  - IngestRequest: batch of up to 500 events
  - IngestError: per-event error detail
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = 1


class EventModel(BaseModel):
    """Single detection event from the pipeline."""
    event_id: str = Field(..., description="UUID v4 unique event identifier")
    store_id: str = Field(..., max_length=20)
    camera_id: str = Field(..., max_length=50)
    visitor_id: str = Field(..., max_length=20)
    event_type: str = Field(..., description="One of the 8 valid event types")
    timestamp: datetime
    zone_id: Optional[str] = Field(None, max_length=50)
    dwell_ms: int = Field(0, ge=0)
    is_staff: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v):
        valid = {e.value for e in EventType}
        if v not in valid:
            raise ValueError(
                f"event_type '{v}' is not in allowed catalogue. "
                f"Must be one of: {', '.join(sorted(valid))}"
            )
        return v

    @field_validator("event_id")
    @classmethod
    def validate_uuid_format(cls, v):
        """Validate event_id looks like a UUID."""
        import uuid
        try:
            uuid.UUID(v, version=4)
        except ValueError:
            raise ValueError(f"event_id '{v}' is not a valid UUID v4")
        return v


class IngestRequest(BaseModel):
    """Batch ingest request — max 500 events."""
    events: List[EventModel] = Field(..., max_length=500)


class IngestError(BaseModel):
    """Error detail for a rejected event."""
    index: int
    event_id: str
    reason: str
