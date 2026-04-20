"""
VenueFlow – Input validators.
Centralised validation logic, reused across routers.
"""
from __future__ import annotations
import re
from fastapi import HTTPException, status

ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "image/jpeg", "image/png", "image/webp"
})
MAX_IMAGE_BYTES: int = 5 * 1024 * 1024  # 5 MB
GATE_PATTERN: re.Pattern = re.compile(r"^[A-Z0-9]{1,10}$", re.IGNORECASE)


def validate_image_upload(content_type: str, size: int) -> None:
    """
    Validate uploaded image content type and size.

    Args:
        content_type: MIME type string from upload header.
        size: File size in bytes.

    Raises:
        HTTPException 415 if MIME type not allowed.
        HTTPException 413 if file exceeds size limit.
    """
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported media type '{content_type}'. "
                f"Accepted: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            ),
        )
    if size > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size:,} bytes exceeds limit of {MAX_IMAGE_BYTES:,} bytes.",
        )


def validate_gate_id(gate_id: str) -> str:
    """
    Validate and normalise a gate/zone identifier.

    Args:
        gate_id: Raw gate identifier string.

    Returns:
        Uppercased gate identifier.

    Raises:
        HTTPException 400 if format is invalid.
    """
    if not GATE_PATTERN.match(gate_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gate ID '{gate_id}'. Must be 1-10 alphanumeric characters.",
        )
    return gate_id.upper()
