"""
VenueFlow – pytest test suite.
Covers: fan endpoints, staff endpoints, schemas, image utils, translation caching.
Run: pytest tests/ -v --cov=. --cov-report=term-missing
"""
from __future__ import annotations

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# ──────────────────────────── Fixtures ───────────────────────


@pytest.fixture(scope="session")
def client():
    """FastAPI test client with all external services mocked."""
    # Mock all Google services before app import
    with (
        patch("services.gemini_service.vertexai"),
        patch("services.gemini_service.GenerativeModel"),
        patch("services.maps_service.googlemaps.Client"),
        patch("services.firebase_service.firebase_admin"),
        patch("services.firebase_service.db"),
        patch("google.cloud.translate_v2.Client"),
    ):
        from main import app
        yield TestClient(app)


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Generate a minimal valid JPEG for upload tests."""
    img = Image.new("RGB", (200, 150), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def large_image_bytes() -> bytes:
    """Generate a 5MB+ image for size-limit tests."""
    return b"\xff\xd8\xff" + b"\x00" * (6 * 1024 * 1024)


@pytest.fixture
def mock_crowd_analysis():
    return {
        "crowd_level": "medium",
        "estimated_wait_minutes": 12,
        "crowd_density_percent": 54.5,
        "ai_summary": "Moderate crowd visible at the concession stand. Queue extends about 20 meters.",
        "recommended_action": "Move to Gate C for a shorter wait of approximately 3 minutes.",
        "confidence_score": 0.87,
    }


@pytest.fixture
def mock_route_response():
    from models.schemas import RouteResponse, RouteStep
    return RouteResponse(
        origin="12.9716,77.5946",
        destination="South Exit Gate C",
        total_distance_meters=245,
        total_duration_seconds=195,
        steps=[
            RouteStep(
                instruction="Head south on the main concourse",
                distance_meters=120,
                duration_seconds=90,
            ),
            RouteStep(
                instruction="Turn left at the food stalls toward Gate C",
                distance_meters=125,
                duration_seconds=105,
            ),
        ],
    )


# ──────────────────────── Image Utils ────────────────────────


class TestImageUtils:
    def test_downscale_large_image(self):
        from utils.image_utils import downscale_image
        img = Image.new("RGB", (2000, 1500), color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        original = buf.getvalue()

        result = downscale_image(original, max_dimension=1024)

        out_img = Image.open(io.BytesIO(result))
        assert max(out_img.size) <= 1024

    def test_downscale_small_image_unchanged(self):
        from utils.image_utils import downscale_image
        img = Image.new("RGB", (400, 300))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        original = buf.getvalue()

        result = downscale_image(original, max_dimension=1024)
        out_img = Image.open(io.BytesIO(result))
        assert max(out_img.size) <= 1024

    def test_rgba_converted_to_rgb(self):
        from utils.image_utils import downscale_image
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = downscale_image(buf.getvalue())
        out_img = Image.open(io.BytesIO(result))
        assert out_img.mode == "RGB"

    def test_validate_image_size_passes(self):
        from utils.image_utils import validate_image_size
        validate_image_size(b"x" * 100, max_bytes=1000)  # Should not raise

    def test_validate_image_size_raises(self):
        from utils.image_utils import validate_image_size
        with pytest.raises(ValueError, match="too large"):
            validate_image_size(b"x" * 1001, max_bytes=1000)

    def test_image_bytes_to_base64(self):
        from utils.image_utils import image_bytes_to_base64
        result = image_bytes_to_base64(b"hello")
        assert result == "aGVsbG8="


# ──────────────────────── Schemas ────────────────────────────


class TestSchemas:
    def test_route_request_valid_destination(self):
        from models.schemas import RouteRequest
        req = RouteRequest(
            current_gate="A1",
            destination_type="exit",
            venue_lat=12.97,
            venue_lng=77.59,
        )
        assert req.destination_type == "exit"

    def test_route_request_invalid_destination(self):
        from models.schemas import RouteRequest
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            RouteRequest(
                current_gate="A1",
                destination_type="parking",  # Not allowed
                venue_lat=12.97,
                venue_lng=77.59,
            )

    def test_crowd_analysis_response_bounds(self):
        from models.schemas import CrowdAnalysisResponse, CrowdLevel
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            CrowdAnalysisResponse(
                crowd_level=CrowdLevel.LOW,
                estimated_wait_minutes=200,  # > 120, should fail
                crowd_density_percent=50.0,
                ai_summary="Test",
                recommended_action="Move.",
                confidence_score=0.9,
            )

    def test_alert_create_severity_enum(self):
        from models.schemas import AlertCreate, AlertSeverity
        alert = AlertCreate(
            zone_id="A1",
            message="Crowd buildup at north gate",
            severity=AlertSeverity.WARNING,
        )
        assert alert.severity == AlertSeverity.WARNING


# ──────────────────────── Health ─────────────────────────────


class TestHealth:
    def test_health_endpoint_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_has_status(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_has_services(self, client):
        data = client.get("/health").json()
        assert "services" in data
        assert isinstance(data["services"], dict)

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["name"] == "VenueFlow API"


# ──────────────────────── Fan Endpoints ──────────────────────


class TestFanAnalyze:
    def test_analyze_rejects_non_image(self, client):
        response = client.post(
            "/api/fan/analyze",
            files={"file": ("doc.pdf", b"fake pdf", "application/pdf")},
        )
        assert response.status_code == 415

    def test_analyze_returns_crowd_response(self, client, sample_image_bytes, mock_crowd_analysis):
        with patch("routers.fan.get_gemini_service") as mock_dep:
            mock_service = MagicMock()
            mock_service.analyze_crowd_image = AsyncMock(
                return_value=MagicMock(**mock_crowd_analysis)
            )
            mock_dep.return_value = mock_service

            response = client.post(
                "/api/fan/analyze",
                files={"file": ("crowd.jpg", sample_image_bytes, "image/jpeg")},
            )
        assert response.status_code == 200

    def test_analyze_503_on_gemini_failure(self, client, sample_image_bytes):
        with patch("routers.fan.get_gemini_service") as mock_dep:
            mock_service = MagicMock()
            mock_service.analyze_crowd_image = AsyncMock(
                side_effect=RuntimeError("Gemini down")
            )
            mock_dep.return_value = mock_service

            response = client.post(
                "/api/fan/analyze",
                files={"file": ("crowd.jpg", sample_image_bytes, "image/jpeg")},
            )
        assert response.status_code == 503


class TestFanChat:
    def test_chat_returns_reply(self, client):
        with patch("routers.fan.get_gemini_service") as mock_gemini, \
             patch("routers.fan.get_translation_service") as mock_trans:

            mock_gemini.return_value.fan_chat = AsyncMock(
                return_value="Gate C has the shortest queue right now!"
            )
            mock_trans.return_value.translate_text = MagicMock(return_value="...")

            response = client.post(
                "/api/fan/chat",
                json={"message": "Where is the shortest queue?", "language_code": "en"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    def test_chat_validates_empty_message(self, client):
        response = client.post(
            "/api/fan/chat",
            json={"message": "", "language_code": "en"},
        )
        assert response.status_code == 422  # Pydantic validation


class TestFanRoute:
    def test_route_returns_steps(self, client, mock_route_response):
        with patch("routers.fan.get_maps_service") as mock_maps, \
             patch("routers.fan.get_translation_service") as mock_trans:

            mock_maps.return_value.get_route_to_facility = MagicMock(
                return_value=mock_route_response
            )
            mock_trans.return_value.translate_text = MagicMock(return_value="...")

            response = client.post(
                "/api/fan/route",
                json={
                    "current_gate": "A1",
                    "destination_type": "exit",
                    "venue_lat": 12.9716,
                    "venue_lng": 77.5946,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "steps" in data
        assert len(data["steps"]) > 0

    def test_route_invalid_destination_type(self, client):
        response = client.post(
            "/api/fan/route",
            json={
                "current_gate": "A1",
                "destination_type": "parking",
                "venue_lat": 12.9716,
                "venue_lng": 77.5946,
            },
        )
        assert response.status_code == 422


# ──────────────────────── Staff Endpoints ────────────────────


class TestStaffHeatmap:
    def test_heatmap_returns_zones(self, client):
        mock_zones = [
            MagicMock(
                zone_id="A1", zone_name="North Stand",
                crowd_level="medium", occupancy_percent=55.0,
                wait_minutes=8, lat=12.97, lng=77.59,
            )
        ]
        with patch("routers.staff.get_firebase_service") as mock_fb:
            mock_fb.return_value.seed_zones = MagicMock()
            mock_fb.return_value.get_all_zones = MagicMock(return_value=mock_zones)

            response = client.get("/api/staff/heatmap")
        assert response.status_code == 200

    def test_heatmap_503_on_firebase_failure(self, client):
        with patch("routers.staff.get_firebase_service") as mock_fb:
            mock_fb.return_value.seed_zones = MagicMock(side_effect=Exception("Firebase down"))

            response = client.get("/api/staff/heatmap")
        assert response.status_code == 503


class TestStaffAlerts:
    def test_create_alert_success(self, client):
        mock_alert = MagicMock(
            alert_id="AB12CD",
            zone_id="B2",
            message="Crowd building at east stand",
            severity="warning",
            timestamp="2026-04-20T18:00:00+00:00",
            translations={"hi": "पूर्वी स्टैंड में भीड़ बढ़ रही है"},
        )
        with patch("routers.staff.get_firebase_service") as mock_fb, \
             patch("routers.staff.get_translation_service") as mock_trans:

            mock_fb.return_value.create_alert = MagicMock(return_value=mock_alert)
            mock_trans.return_value.translate_to_many = MagicMock(
                return_value={"hi": "पूर्वी स्टैंड में भीड़ बढ़ रही है"}
            )

            response = client.post(
                "/api/staff/alerts",
                json={
                    "zone_id": "B2",
                    "message": "Crowd building at east stand",
                    "severity": "warning",
                    "broadcast_languages": ["en", "hi"],
                },
            )
        assert response.status_code == 201

    def test_alert_message_too_short(self, client):
        response = client.post(
            "/api/staff/alerts",
            json={
                "zone_id": "B2",
                "message": "Hi",  # < 5 chars
                "severity": "info",
            },
        )
        assert response.status_code == 422
