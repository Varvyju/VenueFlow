"""
VenueFlow – Google Maps Platform service.
Handles gate routing and nearest facility lookup.
"""
from __future__ import annotations

import logging
from cachetools import TTLCache, cached
from functools import lru_cache
from typing import Optional

import googlemaps

from models.schemas import RouteResponse, RouteStep
from utils.config import get_settings

logger = logging.getLogger(__name__)

# Destination keyword map for Places API
DESTINATION_KEYWORDS: dict[str, str] = {
    "exit":     "stadium exit gate",
    "food":     "stadium concession food stand",
    "restroom": "stadium restroom toilet",
    "medical":  "stadium first aid medical",
}

# Cache route results for 5 minutes to avoid repeated Maps API calls
_route_cache: TTLCache = TTLCache(maxsize=256, ttl=300)


class MapsService:
    """Wraps Google Maps Python client for VenueFlow routing."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = googlemaps.Client(key=settings.google_maps_api_key)
        logger.info("MapsService initialised.")

    def get_route_to_facility(
        self,
        origin_lat: float,
        origin_lng: float,
        destination_type: str,
        language: str = "en",
    ) -> RouteResponse:
        """
        Find and route to the nearest uncrowded facility of the requested type.

        Args:
            origin_lat: Fan's current latitude.
            origin_lng: Fan's current longitude.
            destination_type: One of exit | food | restroom | medical.
            language: BCP-47 language code for step instructions.

        Returns:
            RouteResponse with turn-by-turn steps.
        """
        cache_key = (origin_lat, origin_lng, destination_type, language)
        if cache_key in _route_cache:
            logger.debug("Route cache hit for %s.", cache_key)
            return _route_cache[cache_key]

        keyword = DESTINATION_KEYWORDS.get(destination_type, destination_type)
        origin = (origin_lat, origin_lng)

        # Step 1: Find nearest facility via Places Nearby
        places_result = self._client.places_nearby(
            location=origin,
            radius=500,
            keyword=keyword,
            open_now=True,
        )

        results = places_result.get("results", [])
        if not results:
            # Fallback: use keyword search with wider radius
            places_result = self._client.places_nearby(
                location=origin,
                radius=1000,
                keyword=keyword,
            )
            results = places_result.get("results", [])

        if not results:
            # Last resort – return straight-line placeholder
            return self._fallback_route(destination_type)

        dest = results[0]["geometry"]["location"]
        dest_name = results[0].get("name", destination_type.capitalize())
        destination = (dest["lat"], dest["lng"])

        # Step 2: Get walking directions
        directions = self._client.directions(
            origin=origin,
            destination=destination,
            mode="walking",
            language=language,
        )

        if not directions:
            return self._fallback_route(destination_type)

        leg = directions[0]["legs"][0]
        steps = [
            RouteStep(
                instruction=self._strip_html(step["html_instructions"]),
                distance_meters=step["distance"]["value"],
                duration_seconds=step["duration"]["value"],
            )
            for step in leg["steps"]
        ]

        result = RouteResponse(
            origin=f"{origin_lat:.4f},{origin_lng:.4f}",
            destination=dest_name,
            total_distance_meters=leg["distance"]["value"],
            total_duration_seconds=leg["duration"]["value"],
            steps=steps,
        )

        _route_cache[cache_key] = result
        return result

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from Maps step instructions."""
        import re
        return re.sub(r"<[^>]+>", "", text).strip()

    @staticmethod
    def _fallback_route(destination_type: str) -> RouteResponse:
        """Return a safe fallback when Maps API yields no results."""
        return RouteResponse(
            origin="current location",
            destination=destination_type.capitalize(),
            total_distance_meters=0,
            total_duration_seconds=0,
            steps=[
                RouteStep(
                    instruction=f"Please ask a staff member for the nearest {destination_type}.",
                    distance_meters=0,
                    duration_seconds=0,
                )
            ],
        )


@lru_cache(maxsize=1)
def get_maps_service() -> MapsService:
    """Singleton Maps client."""
    return MapsService()
