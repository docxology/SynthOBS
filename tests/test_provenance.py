"""Real-data tests for :mod:`synthobs.provenance`.

Every test exercises actual byte packing, real SHA-256, and real RGBA
bytearrays. All computation and file buffers are real.
"""

from __future__ import annotations

import hashlib
import struct

import pytest

from synthobs.provenance import (
    AUTHENTICATED_PAYLOAD_SIZE,
    CHECKSUM_SIZE,
    LENGTH_PREFIX_SIZE,
    PAYLOAD_SIZE,
    RECORD_SIZE,
    ProvenanceError,
    TelemetryRecord,
    build_authenticated_payload,
    build_payload,
    canonical_bytes,
    embed_lsb,
    extract_lsb,
    provenance_digest,
    short_signature,
    signature_bits,
    verify_authenticated_payload,
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


def test_signature_bits_are_digest_prefix_bits() -> None:
    assert signature_bits("80ff0001") == (
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
    )


@pytest.mark.parametrize("signature", ["", "abc", "zzzzzzzz", b"80ff0001"])
def test_signature_bits_fail_closed(signature) -> None:
    with pytest.raises(ProvenanceError, match="signature"):
        signature_bits(signature)  # type: ignore[arg-type]


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


def test_authenticated_payload_round_trips_with_secret_key() -> None:
    key = b"local verifier key, never serialized"
    payload = build_authenticated_payload(_record(), key)
    assert len(payload) == AUTHENTICATED_PAYLOAD_SIZE
    recovered = verify_authenticated_payload(payload, key)
    assert recovered == verify_payload(payload[:PAYLOAD_SIZE])


def test_authenticated_payload_rejects_wrong_key_and_recomputed_checksum() -> None:
    key = b"correct key"
    payload = build_authenticated_payload(_record(), key)
    with pytest.raises(ProvenanceError, match="HMAC mismatch"):
        verify_authenticated_payload(payload, b"wrong key")

    forged_record = TelemetryRecord(999.0, 87, 421.0, 0.73, 1.04, 1_718_000_000)
    forged = build_payload(forged_record) + payload[PAYLOAD_SIZE:]
    assert verify_payload(forged[:PAYLOAD_SIZE]).flux == pytest.approx(999.0)
    with pytest.raises(ProvenanceError, match="HMAC mismatch"):
        verify_authenticated_payload(forged, key)


@pytest.mark.parametrize("bad_key", [b"", bytearray(), "text"])
def test_authenticated_payload_rejects_empty_or_non_bytes_key(bad_key) -> None:
    with pytest.raises(ProvenanceError, match="HMAC key"):
        build_authenticated_payload(_record(), bad_key)  # type: ignore[arg-type]


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


def test_embed_rejects_payload_larger_than_uint16_prefix() -> None:
    width, height = 1024, 1024
    rgba = _blank_buffer(width, height)
    with pytest.raises(ProvenanceError, match="uint16 length prefix"):
        embed_lsb(rgba, width, height, b"x" * 0x1_0000)


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
        ({"sunspots": 0x80000000}, "int32 range"),
        ({"lock_strength": 1.5}, r"lock_strength must be in \[0, 1\]"),
        ({"lock_strength": -0.1}, r"lock_strength must be in \[0, 1\]"),
        ({"solar_wind_kms": 0.0}, "solar_wind_kms must be > 0"),
        ({"solar_wind_kms": -1.0}, "solar_wind_kms must be > 0"),
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
    with pytest.raises(ProvenanceError, match="observed_unix must be an int"):
        TelemetryRecord(**{**base, "observed_unix": True})  # type: ignore[arg-type]


def test_canonical_bytes_rejects_non_record() -> None:
    with pytest.raises(ProvenanceError, match="requires a TelemetryRecord"):
        canonical_bytes(b"not a record")  # type: ignore[arg-type]


def test_verify_payload_rejects_non_bytes() -> None:
    with pytest.raises(ProvenanceError, match="must be bytes"):
        verify_payload(12345)  # type: ignore[arg-type]


def test_verify_payload_accepts_bytearray() -> None:
    rec = _record()
    recovered = verify_payload(bytearray(build_payload(rec)))
    assert short_signature(recovered) == short_signature(rec)


def test_extract_buffer_too_small_for_header_raises() -> None:
    # 1x1 RGBA => 1 blue LSB, cannot hold the 16-bit length prefix.
    with pytest.raises(ProvenanceError, match="length prefix"):
        extract_lsb(b"\x00\x00\x00\x00", 1, 1)


def test_unpacked_invalid_record_fails_closed() -> None:
    """A payload whose body decodes to an invalid record fails on verify."""
    # Hand-build a body with flux = 0 (invalid), recompute a valid checksum so
    # the tamper check passes and the record validation is what trips.
    body = struct.pack("<f i f f f I", 0.0, 1, 400.0, 0.5, 0.1, 1_000)
    checksum = hashlib.sha256(body).digest()[:CHECKSUM_SIZE]
    with pytest.raises(ProvenanceError, match="flux must be > 0"):
        verify_payload(body + checksum)


def test_record_is_frozen() -> None:
    rec = _record()
    with pytest.raises(Exception):
        rec.flux = 1.0  # type: ignore[misc]


def test_read_blue_bits_rejects_non_byte_aligned_count() -> None:
    """A non-multiple-of-8 bit count must fail closed, not silently truncate.

    ``bytearray(n_bits // 8)`` rounds down, so requesting 12 bits would size a
    1-byte buffer and drop the trailing 4 bits. The guard raises instead.
    """
    from synthobs.provenance import _read_blue_bits

    rgba = bytes(4 * 8)  # 8 pixels, enough blue LSBs for the read attempt
    for bad in (1, 7, 12, 15):
        with pytest.raises(ProvenanceError, match="multiple of 8"):
            _read_blue_bits(rgba, 0, bad)

    # A byte-aligned request on the same buffer still works (no false positive).
    assert _read_blue_bits(rgba, 0, 8) == b"\x00"
