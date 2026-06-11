"""Real-data tests for :mod:`synthobs.provenance` (no mocks).

Every test exercises actual byte packing, real SHA-256, and real RGBA
bytearrays. There are no mocks, no patches, and no stubbed I/O.
"""

from __future__ import annotations

import hashlib
import struct

import pytest

from synthobs.provenance import (
    CHECKSUM_SIZE,
    LENGTH_PREFIX_SIZE,
    PAYLOAD_SIZE,
    RECORD_SIZE,
    ProvenanceError,
    TelemetryRecord,
    build_payload,
    canonical_bytes,
    embed_lsb,
    extract_lsb,
    provenance_digest,
    short_signature,
    verify_payload,
)


def _record() -> TelemetryRecord:
    """A representative, valid live-telemetry snapshot."""
    return TelemetryRecord(
        flux=152.5,
        sunspots=87,
        solar_wind_kms=421.0,
        lock_strength=0.73,
        phase_bias_rad=1.04,
        observed_unix=1_718_000_000,
    )


def _blank_buffer(width: int, height: int, fill: int = 0) -> bytearray:
    """An RGBA buffer of the right size, every byte set to ``fill``."""
    return bytearray([fill]) * (width * height * 4)


# --- canonical_bytes / record round-trip ----------------------------------- #


def test_canonical_bytes_is_fixed_length() -> None:
    assert len(canonical_bytes(_record())) == RECORD_SIZE == 24


def test_canonical_bytes_layout_offsets() -> None:
    """Each field lands at its documented offset, little-endian."""
    rec = _record()
    raw = canonical_bytes(rec)
    assert struct.unpack_from("<f", raw, 0)[0] == pytest.approx(rec.flux, rel=1e-6)
    assert struct.unpack_from("<i", raw, 4)[0] == rec.sunspots
    assert struct.unpack_from("<f", raw, 8)[0] == pytest.approx(
        rec.solar_wind_kms, rel=1e-6
    )
    assert struct.unpack_from("<f", raw, 12)[0] == pytest.approx(
        rec.lock_strength, rel=1e-6
    )
    assert struct.unpack_from("<f", raw, 16)[0] == pytest.approx(
        rec.phase_bias_rad, rel=1e-6
    )
    assert struct.unpack_from("<I", raw, 20)[0] == rec.observed_unix


def test_canonical_bytes_to_record_round_trip() -> None:
    """A record survives canonical_bytes -> verify_payload (float32 projection)."""
    rec = _record()
    recovered = verify_payload(build_payload(rec))
    assert recovered.sunspots == rec.sunspots
    assert recovered.observed_unix == rec.observed_unix
    assert recovered.flux == pytest.approx(rec.flux, rel=1e-6)
    assert recovered.solar_wind_kms == pytest.approx(rec.solar_wind_kms, rel=1e-6)
    assert recovered.lock_strength == pytest.approx(rec.lock_strength, rel=1e-6)
    assert recovered.phase_bias_rad == pytest.approx(rec.phase_bias_rad, rel=1e-6)


# --- digest determinism + sensitivity --------------------------------------- #


def test_digest_is_deterministic() -> None:
    rec = _record()
    assert provenance_digest(rec) == provenance_digest(_record())
    assert len(provenance_digest(rec)) == 64
    assert short_signature(rec) == provenance_digest(rec)[:8]


def test_digest_changes_when_one_field_flips() -> None:
    base = provenance_digest(_record())
    mutants = [
        TelemetryRecord(152.6, 87, 421.0, 0.73, 1.04, 1_718_000_000),
        TelemetryRecord(152.5, 88, 421.0, 0.73, 1.04, 1_718_000_000),
        TelemetryRecord(152.5, 87, 422.0, 0.73, 1.04, 1_718_000_000),
        TelemetryRecord(152.5, 87, 421.0, 0.74, 1.04, 1_718_000_000),
        TelemetryRecord(152.5, 87, 421.0, 0.73, 1.05, 1_718_000_000),
        TelemetryRecord(152.5, 87, 421.0, 0.73, 1.04, 1_718_000_001),
    ]
    for mutant in mutants:
        assert provenance_digest(mutant) != base


# --- build_payload ----------------------------------------------------------- #


def test_build_payload_size_and_checksum() -> None:
    rec = _record()
    payload = build_payload(rec)
    assert len(payload) == PAYLOAD_SIZE == RECORD_SIZE + CHECKSUM_SIZE
    body, checksum = payload[:RECORD_SIZE], payload[RECORD_SIZE:]
    assert body == canonical_bytes(rec)
    assert checksum == hashlib.sha256(body).digest()[:CHECKSUM_SIZE]


# --- embed / extract round-trip --------------------------------------------- #


def test_embed_then_extract_identical_payload() -> None:
    width, height = 64, 64
    rgba = _blank_buffer(width, height, fill=200)
    payload = build_payload(_record())
    embed_lsb(rgba, width, height, payload)
    assert extract_lsb(bytes(rgba), width, height) == payload


def test_embed_leaves_rgb_a_untouched() -> None:
    """Only blue LSBs may change; R, G, A and higher blue bits are preserved."""
    width, height = 32, 32
    before = _blank_buffer(width, height, fill=0xAB)  # 0xAB = ...1010_1011
    after = bytearray(before)
    payload = build_payload(_record())
    embed_lsb(after, width, height, payload)
    for i in range(width * height):
        base = i * 4
        assert after[base + 0] == before[base + 0]  # R
        assert after[base + 1] == before[base + 1]  # G
        assert after[base + 3] == before[base + 3]  # A
        # Blue: only bit 0 may differ.
        assert (after[base + 2] & 0xFE) == (before[base + 2] & 0xFE)


def test_embed_then_verify_returns_original_record() -> None:
    width, height = 48, 48
    rgba = _blank_buffer(width, height, fill=10)
    rec = _record()
    embed_lsb(rgba, width, height, build_payload(rec))
    recovered = verify_payload(extract_lsb(bytes(rgba), width, height))
    assert recovered.sunspots == rec.sunspots
    assert recovered.observed_unix == rec.observed_unix
    assert short_signature(recovered) == short_signature(rec)


# --- tamper evidence --------------------------------------------------------- #


def test_flipping_non_lsb_pixel_bit_is_fine() -> None:
    """Disturbing a higher blue bit (or R/G/A) does not affect recovery."""
    width, height = 40, 40
    rgba = _blank_buffer(width, height, fill=0)
    rec = _record()
    embed_lsb(rgba, width, height, build_payload(rec))
    # Flip bit 1 (not the LSB) of a blue byte well inside the embedded region.
    rgba[10 * 4 + 2] ^= 0b10
    # Flip a red byte too.
    rgba[12 * 4 + 0] ^= 0xFF
    recovered = verify_payload(extract_lsb(bytes(rgba), width, height))
    assert short_signature(recovered) == short_signature(rec)


def test_flipping_embedded_lsb_raises() -> None:
    """Flipping a single embedded blue LSB corrupts the payload -> tamper."""
    width, height = 40, 40
    rgba = _blank_buffer(width, height, fill=0)
    embed_lsb(rgba, width, height, build_payload(_record()))
    # Bit index 40 lands inside the record body; flip that blue LSB.
    blue_pos = 40 * 4 + 2
    rgba[blue_pos] ^= 0b1
    payload = extract_lsb(bytes(rgba), width, height)
    with pytest.raises(ProvenanceError, match="checksum mismatch"):
        verify_payload(payload)


def test_corrupt_payload_body_raises() -> None:
    payload = bytearray(build_payload(_record()))
    payload[0] ^= 0xFF  # disturb the flux bytes, leave checksum intact
    with pytest.raises(ProvenanceError, match="checksum mismatch"):
        verify_payload(bytes(payload))


def test_corrupt_checksum_raises() -> None:
    payload = bytearray(build_payload(_record()))
    payload[-1] ^= 0xFF
    with pytest.raises(ProvenanceError, match="checksum mismatch"):
        verify_payload(bytes(payload))


def test_verify_payload_wrong_size_raises() -> None:
    with pytest.raises(ProvenanceError, match="must be"):
        verify_payload(b"\x00" * (PAYLOAD_SIZE - 1))


# --- buffer-too-small / dimension fail-closed ------------------------------- #


def test_embed_buffer_too_small_raises() -> None:
    """A 4x4 buffer (16 blue LSBs) cannot hold a 28-byte payload."""
    width, height = 4, 4
    rgba = _blank_buffer(width, height)
    with pytest.raises(ProvenanceError, match="need"):
        embed_lsb(rgba, width, height, build_payload(_record()))


def test_embed_wrong_buffer_length_raises() -> None:
    width, height = 16, 16
    rgba = _blank_buffer(width, height)
    rgba.pop()  # now one byte short
    with pytest.raises(ProvenanceError, match="expected"):
        embed_lsb(rgba, width, height, build_payload(_record()))


def test_embed_requires_bytearray() -> None:
    width, height = 16, 16
    immutable = bytes(_blank_buffer(width, height))
    with pytest.raises(ProvenanceError, match="mutable bytearray"):
        embed_lsb(immutable, width, height, build_payload(_record()))  # type: ignore[arg-type]


def test_embed_nonpositive_dimensions_raise() -> None:
    with pytest.raises(ProvenanceError, match="positive"):
        embed_lsb(bytearray(), 0, 10, b"x")


def test_extract_wrong_buffer_length_raises() -> None:
    with pytest.raises(ProvenanceError, match="expected"):
        extract_lsb(b"\x00" * 10, 16, 16)


def test_extract_declared_length_overflow_raises() -> None:
    """A length prefix larger than the buffer can hold fails closed."""
    width, height = 8, 8  # 64 blue LSBs => 8 bytes of capacity
    rgba = _blank_buffer(width, height, fill=0)
    # Write a length prefix of 0xFFFF (MSB-first) into the first 16 blue LSBs.
    big = struct.pack("<H", 0xFFFF)
    for bit_index in range(LENGTH_PREFIX_SIZE * 8):
        bit = (big[bit_index >> 3] >> (7 - (bit_index & 7))) & 1
        rgba[bit_index * 4 + 2] = (rgba[bit_index * 4 + 2] & 0xFE) | bit
    with pytest.raises(ProvenanceError, match="exceeds buffer capacity"):
        extract_lsb(bytes(rgba), width, height)


# --- fail-closed record validation ------------------------------------------ #


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"flux": 0.0}, "flux must be > 0"),
        ({"flux": -3.0}, "flux must be > 0"),
        ({"flux": float("nan")}, "finite"),
        ({"flux": float("inf")}, "finite"),
        ({"sunspots": -1}, "sunspots must be >= 0"),
        ({"lock_strength": 1.5}, r"lock_strength must be in \[0, 1\]"),
        ({"lock_strength": -0.1}, r"lock_strength must be in \[0, 1\]"),
        ({"solar_wind_kms": float("nan")}, "finite"),
        ({"phase_bias_rad": float("inf")}, "finite"),
        ({"observed_unix": -1}, "uint32"),
        ({"observed_unix": 0x1_0000_0000}, "uint32"),
    ],
)
def test_invalid_record_fields_fail_closed(kwargs: dict, match: str) -> None:
    base = dict(
        flux=152.5,
        sunspots=87,
        solar_wind_kms=421.0,
        lock_strength=0.73,
        phase_bias_rad=1.04,
        observed_unix=1_718_000_000,
    )
    base.update(kwargs)
    with pytest.raises(ProvenanceError, match=match):
        TelemetryRecord(**base)  # type: ignore[arg-type]


def test_bool_is_rejected_for_int_fields() -> None:
    base = dict(
        flux=152.5,
        sunspots=87,
        solar_wind_kms=421.0,
        lock_strength=0.73,
        phase_bias_rad=1.04,
        observed_unix=1_718_000_000,
    )
    with pytest.raises(ProvenanceError, match="sunspots must be an int"):
        TelemetryRecord(**{**base, "sunspots": True})  # type: ignore[arg-type]


def test_record_is_frozen() -> None:
    rec = _record()
    with pytest.raises(Exception):
        rec.flux = 1.0  # type: ignore[misc]
