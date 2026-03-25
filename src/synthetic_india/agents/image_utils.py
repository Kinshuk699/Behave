"""Image encoding utilities for vision-native evaluation."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path


def encode_image(image_path: str) -> tuple[str, str]:
    """Read an image file and return (base64_string, media_type).

    Supports PNG, JPEG, GIF, and WebP — the formats accepted by
    Anthropic's vision API.
    """
    path = Path(image_path)
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")

    media_type, _ = mimetypes.guess_type(str(path))
    if media_type is None:
        media_type = "image/png"  # safe default

    return b64, media_type
