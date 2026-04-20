"""
VenueFlow – Pydantic schemas.
All I/O types are strictly validated here, keeping routers clean.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────── Enums ───────────────────────────

class CrowdLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    INFO    = "info"
    WARNING = "warning"
    DANGER  = "danger"


# ─────────────────────────── Fan ─────────────────────────────

class CrowdAnalysisResponse(BaseModel):
    crowd_level: CrowdLevel
    estimated_wait_minutes: int = Field(ge=0, le=120)
    crowd_density_percent: float = Field(ge=0.0, le=100.0)
    ai_summary: str
    recommended_action: str
    confidence_score: float = Field(ge=0.0, le=1.0)


class RouteRequest(BaseModel):
    current_gate: str = Field(..., min_length=1, max_length=50)
    destination_type: str = Field(..., description="exit | food | restroom | medical")
    venue_lat: float = Field(..., ge=-90.0, le=90.0)
    venue_lng: float = Field(..., ge=-180.0, le=180.0)
    language_code: str = Field(default="en", min_length=2, max_length=10)

    @field_validator("destination_type")
    @classmethod
    def validate_destination(cls, v: str) -> str:
        allowed = {"exit", "food", "restroom", "medical"}
        if v not in allowed:
            raise ValueError(f"destination_type must be one of {allowed}")
        return v


class RouteStep(BaseModel):
    instruction: str
    distance_meters: int
    duration_seconds: int


class RouteResponse(BaseModel):
    origin: str
    destination: str
    total_distance_meters: int
    total_duration_seconds: int
    steps: list[RouteStep]
    translated_summary: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    language_code: str = Field(default="en")
    venue_context: Optional[str] = Field(default="large sporting venue")


class ChatResponse(BaseModel):
    reply: str
    translated_reply: Optional[str] = None


# ─────────────────────────── Staff ───────────────────────────

class ZoneData(BaseModel):
    zone_id: str
    zone_name: str
    crowd_level: CrowdLevel
    occupancy_percent: float = Field(ge=0.0, le=100.0)
    wait_minutes: int = Field(ge=0)
    lat: float
    lng: float


class HeatmapResponse(BaseModel):
    venue_id: str
    timestamp: str
    zones: list[ZoneData]
    overall_crowd_level: CrowdLevel
    total_occupancy_percent: float


class AlertCreate(BaseModel):
    zone_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=5, max_length=500)
    severity: AlertSeverity
    broadcast_languages: list[str] = Field(default=["en"])


class AlertResponse(BaseModel):
    alert_id: str
    zone_id: str
    message: str
    severity: AlertSeverity
    timestamp: str
    translations: dict[str, str] = {}


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    target_languages: list[str] = Field(..., min_length=1, max_length=10)


class TranslateResponse(BaseModel):
    original: str
    translations: dict[str, str]


# ─────────────────────────── Health ──────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, bool]
