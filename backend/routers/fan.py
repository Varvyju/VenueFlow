"""
VenueFlow – Fan-facing API router.
Endpoints: crowd photo analysis, AI chat, facility routing.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from models.schemas import (
    ChatRequest, ChatResponse,
    CrowdAnalysisResponse,
    RouteRequest, RouteResponse,
    TranslateRequest, TranslateResponse,
)
from services.gemini_service import GeminiService, get_gemini_service
from services.maps_service import MapsService, get_maps_service
from services.translation_service import TranslationService, get_translation_service
from utils.config import get_settings
from utils.image_utils import validate_image_size

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fan", tags=["Fan"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ──────────────── Crowd Analysis ─────────────────

@router.post(
    "/analyze",
    response_model=CrowdAnalysisResponse,
    summary="Analyse a crowd photo",
    description="Upload a crowd photo. Gemini Vision estimates density, wait time, and routes alternatives.",
)
async def analyze_crowd(
    file: UploadFile = File(..., description="JPEG/PNG crowd photo"),
    gemini: GeminiService = Depends(get_gemini_service),
) -> CrowdAnalysisResponse:
    """
    Accepts an image upload, validates it, downscales via LANCZOS,
    and calls Gemini Vision for crowd analysis.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file.content_type}' not supported. Use JPEG, PNG, or WebP.",
        )

    image_bytes = await file.read()

    settings = get_settings()
    try:
        validate_image_size(image_bytes, settings.max_image_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    try:
        result = await gemini.analyze_crowd_image(image_bytes)
    except Exception as exc:
        logger.error("Gemini crowd analysis failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis service temporarily unavailable. Please try again.",
        ) from exc

    return result


# ──────────────── AI Chat Assistant ──────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the VenueFlow AI assistant",
    description="Natural language Q&A for fans. Answers about queues, facilities, and navigation.",
)
async def fan_chat(
    request: ChatRequest,
    gemini: GeminiService = Depends(get_gemini_service),
    translator: TranslationService = Depends(get_translation_service),
) -> ChatResponse:
    """
    Routes fan questions to Gemini, then optionally translates
    the response back to the fan's preferred language.
    """
    try:
        reply = await gemini.fan_chat(request.message, request.venue_context or "large sporting venue")
    except Exception as exc:
        logger.error("Fan chat failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI assistant is temporarily unavailable.",
        ) from exc

    translated_reply = None
    if request.language_code and request.language_code != "en":
        translated_reply = translator.translate_text(reply, request.language_code)

    return ChatResponse(reply=reply, translated_reply=translated_reply)


# ──────────────── Route to Facility ──────────────

@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Get walking route to nearest facility",
    description="Returns step-by-step walking directions to the nearest exit, food, restroom, or medical point.",
)
async def get_route(
    request: RouteRequest,
    maps: MapsService = Depends(get_maps_service),
    translator: TranslationService = Depends(get_translation_service),
) -> RouteResponse:
    """
    Finds the nearest facility using Google Places Nearby,
    then retrieves walking directions. Translates if needed.
    """
    try:
        route = maps.get_route_to_facility(
            origin_lat=request.venue_lat,
            origin_lng=request.venue_lng,
            destination_type=request.destination_type,
            language=request.language_code,
        )
    except Exception as exc:
        logger.error("Maps routing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing service temporarily unavailable.",
        ) from exc

    if request.language_code != "en":
        summary = f"Head to {route.destination} — {route.total_duration_seconds // 60} min walk."
        route.translated_summary = translator.translate_text(summary, request.language_code)

    return route


# ──────────────── Translate Announcement ─────────

@router.post(
    "/translate",
    response_model=TranslateResponse,
    summary="Translate a venue announcement",
    description="Translate text into multiple languages for multilingual fan support.",
)
async def translate_announcement(
    request: TranslateRequest,
    translator: TranslationService = Depends(get_translation_service),
) -> TranslateResponse:
    translations = translator.translate_to_many(request.text, request.target_languages)
    return TranslateResponse(original=request.text, translations=translations)
