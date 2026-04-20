"""
VenueFlow – Staff Operations API router.
Endpoints: live heatmap, alert management, AI crowd insights.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from models.schemas import (
    AlertCreate, AlertResponse,
    HeatmapResponse, CrowdLevel,
    ZoneData,
)
from services.firebase_service import FirebaseService, get_firebase_service
from services.gemini_service import GeminiService, get_gemini_service
from services.translation_service import TranslationService, get_translation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/staff", tags=["Staff"])


def _compute_overall_level(zones: list[ZoneData]) -> tuple[CrowdLevel, float]:
    """Compute weighted average occupancy and overall crowd level."""
    if not zones:
        return CrowdLevel.LOW, 0.0
    avg = sum(z.occupancy_percent for z in zones) / len(zones)
    if avg >= 85:
        level = CrowdLevel.CRITICAL
    elif avg >= 65:
        level = CrowdLevel.HIGH
    elif avg >= 40:
        level = CrowdLevel.MEDIUM
    else:
        level = CrowdLevel.LOW
    return level, round(avg, 1)


# ──────────────── Heatmap ────────────────────────

@router.get(
    "/heatmap",
    response_model=HeatmapResponse,
    summary="Live crowd density heatmap",
    description="Returns real-time occupancy data for all venue zones, sourced from Firebase.",
)
async def get_heatmap(
    venue_id: str = Query(default="venue_001", description="Venue identifier"),
    firebase: FirebaseService = Depends(get_firebase_service),
) -> HeatmapResponse:
    """Fetches all zone data from Firebase Realtime DB and computes overall metrics."""
    try:
        firebase.seed_zones()  # No-op if already seeded
        zones = firebase.get_all_zones()
    except Exception as exc:
        logger.error("Firebase heatmap fetch failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live data service temporarily unavailable.",
        ) from exc

    overall_level, avg_occupancy = _compute_overall_level(zones)

    return HeatmapResponse(
        venue_id=venue_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        zones=zones,
        overall_crowd_level=overall_level,
        total_occupancy_percent=avg_occupancy,
    )


# ──────────────── Zone Update ─────────────────────

@router.patch(
    "/zone/{zone_id}",
    summary="Update zone occupancy",
    description="Staff updates occupancy for a specific zone in real time.",
)
async def update_zone(
    zone_id: str,
    occupancy_percent: float = Query(..., ge=0.0, le=100.0),
    wait_minutes: int = Query(..., ge=0, le=120),
    firebase: FirebaseService = Depends(get_firebase_service),
) -> dict:
    crowd_level = (
        CrowdLevel.CRITICAL if occupancy_percent >= 85 else
        CrowdLevel.HIGH     if occupancy_percent >= 65 else
        CrowdLevel.MEDIUM   if occupancy_percent >= 40 else
        CrowdLevel.LOW
    )
    try:
        firebase.update_zone(zone_id, {
            "occupancy_percent": occupancy_percent,
            "wait_minutes": wait_minutes,
            "crowd_level": crowd_level.value,
        })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"zone_id": zone_id, "updated": True, "crowd_level": crowd_level}


# ──────────────── Alerts ─────────────────────────

@router.post(
    "/alerts",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and broadcast a crowd alert",
    description="Staff creates an alert which is translated into requested languages and stored in Firebase.",
)
async def create_alert(
    payload: AlertCreate,
    firebase: FirebaseService = Depends(get_firebase_service),
    translator: TranslationService = Depends(get_translation_service),
) -> AlertResponse:
    translations = translator.translate_to_many(
        payload.message,
        [l for l in payload.broadcast_languages if l != "en"],
    )
    try:
        alert = firebase.create_alert(
            zone_id=payload.zone_id,
            message=payload.message,
            severity=payload.severity,
            translations=translations,
        )
    except Exception as exc:
        logger.error("Alert creation failed: %s", exc)
        raise HTTPException(status_code=503, detail="Could not persist alert.") from exc

    return alert


@router.get(
    "/alerts",
    response_model=list[AlertResponse],
    summary="Fetch recent alerts",
)
async def get_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    firebase: FirebaseService = Depends(get_firebase_service),
) -> list[AlertResponse]:
    return firebase.get_recent_alerts(limit=limit)


# ──────────────── AI Staff Insights ──────────────

@router.get(
    "/insights",
    summary="AI-generated staff deployment recommendations",
    description="Gemini analyses current zone data and returns actionable staff deployment advice.",
)
async def get_staff_insights(
    firebase: FirebaseService = Depends(get_firebase_service),
    gemini: GeminiService = Depends(get_gemini_service),
) -> dict:
    zones = firebase.get_all_zones()
    zone_summary = json.dumps(
        [z.model_dump() for z in zones],
        indent=2,
    )
    try:
        insights = await gemini.generate_staff_insight(zone_summary)
    except Exception as exc:
        logger.error("Staff insights generation failed: %s", exc)
        raise HTTPException(status_code=503, detail="AI insights unavailable.") from exc

    return {
        "insights": insights,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "zones_analyzed": len(zones),
    }
