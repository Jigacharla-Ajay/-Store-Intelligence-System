"""
Pydantic v2 response models for all API endpoints.

Response shapes match api_catalog.md exactly.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# POST /events/ingest response
# ---------------------------------------------------------------------------

class IngestErrorDetail(BaseModel):
    index: int
    event_id: str
    reason: str


class IngestResponse(BaseModel):
    accepted: int = 0
    rejected: int = 0
    duplicate: int = 0
    errors: List[IngestErrorDetail] = Field(default_factory=list)
    trace_id: str = ""


# ---------------------------------------------------------------------------
# GET /stores/{id}/metrics response
# ---------------------------------------------------------------------------

class VisitorMetrics(BaseModel):
    unique_count: int = 0
    total_entries: int = 0
    reentry_count: int = 0


class ConversionMetrics(BaseModel):
    rate: float = 0.0
    converted_visitors: int = 0
    total_visitors: int = 0


class DwellMetrics(BaseModel):
    avg_total_ms: int = 0
    by_zone: Dict[str, int] = Field(default_factory=dict)


class QueueMetrics(BaseModel):
    current_depth: int = 0
    max_depth_today: int = 0
    avg_wait_ms: int = 0


class AbandonmentMetrics(BaseModel):
    rate: float = 0.0
    abandoned_count: int = 0
    billing_entries: int = 0


class TimeWindow(BaseModel):
    from_time: datetime = Field(..., alias="from")
    to_time: datetime = Field(..., alias="to")

    model_config = {"populate_by_name": True}


class MetricsResponse(BaseModel):
    store_id: str
    computed_at: datetime
    window: TimeWindow
    visitors: VisitorMetrics
    conversion: ConversionMetrics
    dwell: DwellMetrics
    queue: QueueMetrics
    abandonment: AbandonmentMetrics


# ---------------------------------------------------------------------------
# GET /stores/{id}/funnel response
# ---------------------------------------------------------------------------

class FunnelStage(BaseModel):
    stage: str
    label: str
    sessions: int = 0
    dropoff_pct: float = 0.0


class FunnelResponse(BaseModel):
    store_id: str
    date: str
    funnel: List[FunnelStage]
    overall_conversion_pct: float = 0.0
    largest_dropoff_stage: str = ""


# ---------------------------------------------------------------------------
# GET /stores/{id}/heatmap response
# ---------------------------------------------------------------------------

class ZoneHeatmapEntry(BaseModel):
    zone_id: str
    label: str
    visit_count: int = 0
    avg_dwell_ms: int = 0
    visit_score: int = 0
    dwell_score: int = 0


class HeatmapResponse(BaseModel):
    store_id: str
    window_minutes: int
    computed_at: datetime
    data_confidence: str = "HIGH"
    zones: List[ZoneHeatmapEntry]


# ---------------------------------------------------------------------------
# GET /stores/{id}/anomalies response
# ---------------------------------------------------------------------------

class AnomalyEntry(BaseModel):
    anomaly_id: str
    type: str
    severity: str
    detected_at: datetime
    description: str
    suggested_action: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnomalyResponse(BaseModel):
    store_id: str
    checked_at: datetime
    active_anomalies: List[AnomalyEntry]
    anomaly_count: int = 0


# ---------------------------------------------------------------------------
# GET /health response
# ---------------------------------------------------------------------------

class StoreHealth(BaseModel):
    store_id: str
    last_event_at: Optional[datetime] = None
    lag_seconds: int = 0
    feed_status: str = "NO_DATA"


class HealthResponse(BaseModel):
    status: str = "healthy"
    checked_at: datetime
    database: str = "connected"
    redis: str = "connected"
    stores: List[StoreHealth] = Field(default_factory=list)
    uptime_seconds: int = 0
    error: Optional[str] = None
    trace_id: Optional[str] = None
