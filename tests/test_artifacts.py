"""Engine-side artifact inspection tests (promotion-boundary logic)."""

from __future__ import annotations

import hashlib
import io
import struct
import wave

import pytest

from synthobs.artifacts import (
    ArtifactError,
    png_dimensions,
    sha256_bytes,
    wav_metadata,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_bytes(width: int, height: int) -> bytes:
    return (
        PNG_SIGNATURE
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )


def _wav_bytes(
    frames: bytes = b"\x00\x00" * 8,
    *,
    rate: int = 48000,
    channels: int = 1,
    width: int = 2,
) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setframerate(rate)
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.writeframes(frames)
    return buffer.getvalue()


def test_sha256_bytes_matches_hashlib_reference() -> None:
    data = b"synthobs promotion bytes"
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()
    assert (
        sha256_bytes(b"")
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_png_dimensions_reads_ihdr_header() -> None:
    assert png_dimensions(_png_bytes(3200, 2000)) == (3200, 2000)
    assert png_dimensions(_png_bytes(1, 1)) == (1, 1)


def test_png_dimensions_fails_closed_on_malformed_bytes() -> None:
    with pytest.raises(ArtifactError, match="not a valid PNG"):
        png_dimensions(b"GIF89a" + b"\x00" * 32)
    with pytest.raises(ArtifactError, match="not a valid PNG"):
        png_dimensions(PNG_SIGNATURE[:4])


def test_wav_metadata_reports_pcm_fields() -> None:
    meta = wav_metadata(_wav_bytes(rate=44100, channels=2))
    assert meta["media_type"] == "audio/wav"
    assert meta["sample_rate_hz"] == 44100
    assert meta["channels"] == 2
    assert meta["sample_width_bits"] == 16
    assert meta["frames"] == 4


def test_wav_metadata_fails_closed_on_malformed_bytes() -> None:
    with pytest.raises(ArtifactError, match="not a valid WAV"):
        wav_metadata(b"definitely not a RIFF stream")
