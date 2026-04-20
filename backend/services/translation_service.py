"""
VenueFlow – Google Cloud Translation service.
Supports multilingual fan announcements and route instructions.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from cachetools import TTLCache
from google.cloud import translate_v2 as translate

from utils.config import get_settings

logger = logging.getLogger(__name__)

# Cache translations: key=(text, target_lang), TTL=1 hour
_translation_cache: TTLCache = TTLCache(maxsize=1024, ttl=3600)

# Supported stadium announcement languages
SUPPORTED_LANGUAGES: list[str] = [
    "en", "hi", "kn", "ta", "te", "ml",  # Indian languages
    "es", "fr", "de", "pt", "ar",         # International
    "zh", "ja", "ko",                      # Asian
]


class TranslationService:
    """Wraps Google Cloud Translation v2 API."""

    def __init__(self) -> None:
        self._client = translate.Client()
        logger.info("TranslationService initialised.")

    def translate_text(self, text: str, target_language: str) -> str:
        """
        Translate text to the target language.
        Results are cached by (text, target_language) pair.

        Args:
            text: Source text to translate.
            target_language: BCP-47 language code (e.g. "hi", "es").

        Returns:
            Translated string, or original text on failure.
        """
        if target_language == "en":
            return text

        cache_key = (text[:200], target_language)
        if cache_key in _translation_cache:
            logger.debug("Translation cache hit: lang=%s.", target_language)
            return _translation_cache[cache_key]

        try:
            result = self._client.translate(text, target_language=target_language)
            translated = result["translatedText"]
            _translation_cache[cache_key] = translated
            logger.info("Translated to %s (%.0f chars).", target_language, len(translated))
            return translated
        except Exception as exc:
            logger.warning("Translation failed for lang=%s: %s", target_language, exc)
            return text  # Graceful degradation

    def translate_to_many(
        self, text: str, target_languages: list[str]
    ) -> dict[str, str]:
        """
        Translate text into multiple languages at once.

        Args:
            text: Source text.
            target_languages: List of BCP-47 codes.

        Returns:
            Dict mapping language code → translated text.
        """
        return {lang: self.translate_text(text, lang) for lang in target_languages}

    def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.

        Returns:
            BCP-47 language code string.
        """
        try:
            result = self._client.detect_language(text)
            return result.get("language", "en")
        except Exception as exc:
            logger.warning("Language detection failed: %s", exc)
            return "en"


@lru_cache(maxsize=1)
def get_translation_service() -> TranslationService:
    """Singleton Translation client."""
    return TranslationService()
