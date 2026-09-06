"""Binary artifact inspection for promotion-grade evidence.

The promotion boundary (``scripts/promote_obs_evidence.py``) hashes and
format-checks the exact capture bytes before they become versioned manuscript
assets. That parsing/checksum logic lives here — importable and tested by
``tests/`` — while the script only wires file I/O in, per the engine's
no-I/O convention.
"""

from __future__ import annotations

import hashlib
import io
import struct
import wave

__all__ = [
    "ArtifactError",
    "png_dimensions",
    "sha256_bytes",
    "wav_metadata",
]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ArtifactError(ValueError):
    """Raised when a binary artifact is malformed for its declared media type."""


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of *data* (exact file bytes)."""
    return hashlib.sha256(data).hexdigest()


def png_dimensions(raw: bytes) -> tuple[int, int]:
    """Return ``(width, height)`` from the IHDR header of PNG bytes.

    Raises:
        ArtifactError: if the bytes lack the PNG signature or a full IHDR
            header.
    """
    if raw[:8] != PNG_SIGNATURE or len(raw) < 24:
        raise ArtifactError("not a valid PNG capture")
    return struct.unpack(">II", raw[16:24])


def wav_metadata(raw: bytes) -> dict[str, int | str]:
    """Return PCM metadata for WAV bytes as a promotion-manifest fragment.

    Raises:
        ArtifactError: if the bytes are not a decodable WAV stream.
    """
    try:
        with wave.open(io.BytesIO(raw), "rb") as handle:
            return {
                "media_type": "audio/wav",
                "sample_rate_hz": handle.getframerate(),
                "channels": handle.getnchannels(),
                "sample_width_bits": handle.getsampwidth() * 8,
                "frames": handle.getnframes(),
            }
    except (EOFError, wave.Error) as exc:
        raise ArtifactError(f"not a valid WAV capture: {exc}") from exc
