"""
VenueFlow – Image processing utilities.
LANCZOS downscaling keeps inference fast and Cloud Run costs low.
"""
from __future__ import annotations

import io
import base64
import logging
from PIL import Image

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1024  # px – balances quality vs. latency


def downscale_image(image_bytes: bytes, max_dimension: int = MAX_DIMENSION) -> bytes:
    """
    Downscale image to max_dimension using LANCZOS resampling.
    Preserves aspect ratio. Returns JPEG bytes.

    Args:
        image_bytes: Raw image bytes from multipart upload.
        max_dimension: Maximum width or height in pixels.

    Returns:
        Compressed JPEG bytes, or original bytes if already within limits.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA/P to RGB for JPEG compatibility
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    width, height = img.size
    if max(width, height) <= max_dimension:
        logger.debug("Image already within limits (%dx%d), skipping resize.", width, height)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()

    # Maintain aspect ratio
    ratio = max_dimension / max(width, height)
    new_size = (int(width * ratio), int(height * ratio))
    img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    result = buf.getvalue()

    logger.info(
        "Image downscaled %dx%d → %dx%d (%.1f%% size reduction).",
        width, height, new_size[0], new_size[1],
        (1 - len(result) / len(image_bytes)) * 100,
    )
    return result


def image_bytes_to_base64(image_bytes: bytes) -> str:
    """Encode bytes to base64 string for Vertex AI Part."""
    return base64.b64encode(image_bytes).decode("utf-8")


def validate_image_size(image_bytes: bytes, max_bytes: int = 5 * 1024 * 1024) -> None:
    """Raise ValueError if image exceeds max_bytes."""
    if len(image_bytes) > max_bytes:
        raise ValueError(
            f"Image too large: {len(image_bytes):,} bytes. Max allowed: {max_bytes:,} bytes."
        )
