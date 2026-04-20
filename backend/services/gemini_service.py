"""
VenueFlow – Vertex AI Gemini service.
Handles crowd vision analysis + conversational AI assistant.
Falls back gracefully if Vertex AI is unavailable.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Optional

import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    Part,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold,
)

from models.schemas import CrowdAnalysisResponse, CrowdLevel, ChatResponse
from utils.config import get_settings
from utils.image_utils import downscale_image, image_bytes_to_base64

logger = logging.getLogger(__name__)

# ─────────────────────── Safety settings ─────────────────────

SAFETY_SETTINGS = [
    SafetySetting(
        category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
]

# ─────────────────────── System prompts ──────────────────────

CROWD_ANALYSIS_PROMPT = """You are VenueFlow's stadium safety AI.
Analyse the provided crowd image taken at a large sporting venue.

Return ONLY valid JSON matching this exact schema:
{
  "crowd_level": "low|medium|high|critical",
  "estimated_wait_minutes": <int 0-120>,
  "crowd_density_percent": <float 0-100>,
  "ai_summary": "<2 concise sentences describing what you see>",
  "recommended_action": "<1 actionable sentence for the fan>",
  "confidence_score": <float 0.0-1.0>
}

Rules:
- crowd_level "critical" = over 90% density or clearly unsafe conditions
- Be conservative: underestimate density rather than overestimate
- recommended_action must start with an action verb
- Return ONLY the JSON object, no markdown fences"""

FAN_ASSISTANT_SYSTEM_PROMPT = """You are VenueFlow, a helpful stadium assistant AI.
You help fans navigate large sporting venues, find shorter queues, locate facilities,
and have a safe, enjoyable experience.

Guidelines:
- Be concise (2-3 sentences max per response)
- Prioritise safety information
- Suggest alternatives when something is crowded
- Always be friendly and supportive
- If asked something unrelated to venue/stadium topics, politely redirect"""


# ─────────────────────── Service class ───────────────────────

class GeminiService:
    """Wraps Vertex AI Gemini for VenueFlow use cases."""

    def __init__(self) -> None:
        settings = get_settings()
        vertexai.init(
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
        self._vision_model = GenerativeModel(settings.gemini_model)
        self._chat_model = GenerativeModel(
            settings.gemini_model,
            system_instruction=FAN_ASSISTANT_SYSTEM_PROMPT,
        )
        self._generation_config = GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            max_output_tokens=1024,
        )
        logger.info("GeminiService initialised (project=%s).", settings.gcp_project_id)

    async def analyze_crowd_image(self, image_bytes: bytes) -> CrowdAnalysisResponse:
        """
        Run Gemini Vision on a crowd image.
        Downscales first for efficiency, then parses structured JSON output.

        Args:
            image_bytes: Raw bytes from uploaded image file.

        Returns:
            CrowdAnalysisResponse with crowd level, wait time, and recommendations.
        """
        processed = downscale_image(image_bytes)
        b64 = image_bytes_to_base64(processed)

        image_part = Part.from_data(data=b64, mime_type="image/jpeg")
        text_part = Part.from_text(CROWD_ANALYSIS_PROMPT)

        response = self._vision_model.generate_content(
            [image_part, text_part],
            generation_config=self._generation_config,
            safety_settings=SAFETY_SETTINGS,
        )

        raw = response.text.strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        return CrowdAnalysisResponse(**data)

    async def fan_chat(
        self,
        message: str,
        venue_context: str = "large sporting venue",
    ) -> str:
        """
        Single-turn fan assistant response.

        Args:
            message: Fan's question.
            venue_context: Brief venue description for grounding.

        Returns:
            AI response string.
        """
        grounded_message = (
            f"[Venue context: {venue_context}]\nFan question: {message}"
        )
        response = self._chat_model.generate_content(
            grounded_message,
            generation_config=GenerationConfig(
                temperature=0.4,
                max_output_tokens=256,
            ),
            safety_settings=SAFETY_SETTINGS,
        )
        return response.text.strip()

    async def generate_staff_insight(self, zone_summary: str) -> str:
        """
        Generate a staff operations insight from zone crowd data.

        Args:
            zone_summary: JSON string of current zone occupancy data.

        Returns:
            Actionable text recommendation for staff.
        """
        prompt = (
            "You are a crowd safety operations analyst. "
            "Given this stadium zone data, provide 2-3 concise, actionable recommendations "
            "for staff deployment and crowd management. Be direct and prioritise safety.\n\n"
            f"Zone data:\n{zone_summary}"
        )
        response = self._vision_model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.1, max_output_tokens=512),
        )
        return response.text.strip()


@lru_cache(maxsize=1)
def get_gemini_service() -> GeminiService:
    """Singleton – Vertex AI client is expensive to initialise."""
    return GeminiService()
