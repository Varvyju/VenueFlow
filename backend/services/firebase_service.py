"""
VenueFlow – Firebase Realtime Database service.
Stores and streams live zone crowd data for the Staff dashboard.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

from models.schemas import ZoneData, CrowdLevel, AlertResponse, AlertSeverity
from utils.config import get_settings

logger = logging.getLogger(__name__)

# ───────────────────── Default seed data ─────────────────────

DEFAULT_ZONES: list[dict] = [
    {"zone_id": "A1", "zone_name": "North Stand Gate A", "crowd_level": "medium",
     "occupancy_percent": 55.0, "wait_minutes": 8,  "lat": 12.9716, "lng": 77.5946},
    {"zone_id": "B2", "zone_name": "East Concession Stand", "crowd_level": "high",
     "occupancy_percent": 78.0, "wait_minutes": 18, "lat": 12.9720, "lng": 77.5952},
    {"zone_id": "C3", "zone_name": "South Exit Gate C", "crowd_level": "low",
     "occupancy_percent": 22.0, "wait_minutes": 2,  "lat": 12.9710, "lng": 77.5940},
    {"zone_id": "D4", "zone_name": "West Restrooms Block D", "crowd_level": "medium",
     "occupancy_percent": 48.0, "wait_minutes": 6,  "lat": 12.9712, "lng": 77.5958},
    {"zone_id": "E5", "zone_name": "Medical Aid Station E", "crowd_level": "low",
     "occupancy_percent": 10.0, "wait_minutes": 0,  "lat": 12.9718, "lng": 77.5935},
    {"zone_id": "F6", "zone_name": "VIP Entrance Gate F", "crowd_level": "critical",
     "occupancy_percent": 94.0, "wait_minutes": 35, "lat": 12.9724, "lng": 77.5948},
]


class FirebaseService:
    """Wraps Firebase Admin SDK for VenueFlow live data."""

    def __init__(self) -> None:
        settings = get_settings()
        if not firebase_admin._apps:
            cred_path = Path(settings.firebase_credentials_path)
            if cred_path.exists():
                cred = credentials.Certificate(str(cred_path))
            else:
                # Use application default credentials (Cloud Run)
                cred = credentials.ApplicationDefault()

            firebase_admin.initialize_app(cred, {
                "databaseURL": settings.firebase_database_url,
            })
            logger.info("Firebase app initialised.")
        self._db = db

    # ──────────────── Zone operations ────────────────

    def seed_zones(self) -> None:
        """Seed default zone data if not already present."""
        ref = self._db.reference("zones")
        if ref.get() is None:
            for zone in DEFAULT_ZONES:
                ref.child(zone["zone_id"]).set(zone)
            logger.info("Firebase zones seeded with %d zones.", len(DEFAULT_ZONES))

    def get_all_zones(self) -> list[ZoneData]:
        """Fetch all zone occupancy data from Firebase."""
        ref = self._db.reference("zones")
        data = ref.get() or {}
        zones = []
        for zone_id, zone_data in data.items():
            try:
                zones.append(ZoneData(**zone_data))
            except Exception as exc:
                logger.warning("Invalid zone data for %s: %s", zone_id, exc)
        return zones

    def update_zone(self, zone_id: str, updates: dict) -> None:
        """Partial update a zone (e.g., new occupancy reading)."""
        ref = self._db.reference(f"zones/{zone_id}")
        ref.update(updates)
        logger.debug("Zone %s updated: %s", zone_id, updates)

    # ──────────────── Alert operations ───────────────

    def create_alert(
        self,
        zone_id: str,
        message: str,
        severity: AlertSeverity,
        translations: dict[str, str],
    ) -> AlertResponse:
        """Persist a new alert to Firebase and return it."""
        alert_id = str(uuid.uuid4())[:8].upper()
        timestamp = datetime.now(timezone.utc).isoformat()

        alert_data = {
            "alert_id": alert_id,
            "zone_id": zone_id,
            "message": message,
            "severity": severity.value,
            "timestamp": timestamp,
            "translations": translations,
        }

        ref = self._db.reference(f"alerts/{alert_id}")
        ref.set(alert_data)
        logger.info("Alert %s created for zone %s (severity=%s).", alert_id, zone_id, severity)

        return AlertResponse(**alert_data)

    def get_recent_alerts(self, limit: int = 20) -> list[AlertResponse]:
        """Fetch the most recent alerts from Firebase."""
        ref = self._db.reference("alerts")
        data = ref.order_by_child("timestamp").limit_to_last(limit).get() or {}
        alerts = []
        for _, alert_data in data.items():
            try:
                alerts.append(AlertResponse(**alert_data))
            except Exception as exc:
                logger.warning("Invalid alert data: %s", exc)
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)


@lru_cache(maxsize=1)
def get_firebase_service() -> FirebaseService:
    """Singleton Firebase service."""
    return FirebaseService()
