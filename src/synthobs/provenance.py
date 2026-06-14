"""Steganographic provenance for the live SynthOBS overlay.

This module lets a rendered overlay frame carry verifiable, hidden,
tamper-evident proof of the live solar telemetry it was generated from. A
compact :class:`TelemetryRecord` is packed into a fixed-length, byte-exact
little-endian struct, fingerprinted with SHA-256, and embedded into the
least-significant bit of the BLUE channel of an RGBA frame buffer. The
embedded payload carries a 4-byte truncated-SHA-256 checksum so any single
flipped bit in the recovered payload is detected on extraction.

The native C plugin (``plugin/fractisynth``) mirrors this logic. To keep the
mirror trivial the algorithm is integer/byte-exact, uses only stdlib, and the
exact struct layout is documented on :func:`canonical_bytes`. There is one and
only one wire layout; both implementations must agree byte-for-byte.

Design rules (mirrored from the rest of the engine):

* **Fail closed.** Invalid, empty, or tampered input raises a clear exception;
  no silent defaults, no NaN, no truncation.
* **Byte-exact.** Floats are IEEE-754 ``float32``; integers are fixed-width
  little-endian. No locale, no text encoding, no padding ambiguity.
* **Stdlib only.** ``struct`` and ``hashlib`` carry the whole module.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass

__all__ = [
    "ProvenanceError",
    "TelemetryRecord",
    "RECORD_STRUCT",
    "RECORD_SIZE",
    "CHECKSUM_SIZE",
    "PAYLOAD_SIZE",
    "LENGTH_PREFIX_SIZE",
    "SIGNATURE_HEX_SIZE",
    "canonical_bytes",
    "provenance_digest",
    "short_signature",
    "signature_bits",
    "build_payload",
    "embed_lsb",
    "extract_lsb",
    "verify_payload",
]


class ProvenanceError(Exception):
    """Raised on a tamper-evident failure or malformed provenance data.

    Covers checksum mismatch, truncated/oversized payloads, buffers too small
    to embed into, and invalid extracted records.
    """


# --- Canonical wire layout ------------------------------------------------- #
# Little-endian, packed (no implicit alignment padding), 24 bytes total.
#
#   offset  size  type      field            notes
#   ------  ----  --------  ---------------  -----------------------------
#   0       4     float32   flux             IEEE-754, > 0
#   4       4     int32     sunspots         signed, stored >= 0
#   8       4     float32   solar_wind_kms   IEEE-754
#   12      4     float32   lock_strength    IEEE-754, in [0, 1]
#   16      4     float32   phase_bias_rad   IEEE-754
#   20      4     uint32    observed_unix    unsigned seconds since epoch
#
# Format string "<f i f f f I" -> '<' little-endian, no alignment padding,
# fields in declared order. Kept literal and explicit for the C mirror.
RECORD_STRUCT: struct.Struct = struct.Struct("<f i f f f I")
RECORD_SIZE: int = RECORD_STRUCT.size  # == 24
CHECKSUM_SIZE: int = 4
PAYLOAD_SIZE: int = RECORD_SIZE + CHECKSUM_SIZE  # == 28
LENGTH_PREFIX_SIZE: int = 2  # uint16 little-endian payload length
SIGNATURE_HEX_SIZE: int = CHECKSUM_SIZE * 2


@dataclass(frozen=True)
class TelemetryRecord:
    """An immutable snapshot of live solar telemetry that drove a frame.

    Fields:
        flux: F10.7 solar radio flux. Must be finite and strictly positive.
        sunspots: Monitored active-region sunspot count. Must be ``>= 0``.
        solar_wind_kms: Solar wind speed in km/s. Must be finite.
        lock_strength: EGS gateway lock strength in ``[0, 1]``. Must be finite.
        phase_bias_rad: Gateway phase bias in radians. Must be finite.
        observed_unix: Observation time, unsigned seconds since the Unix epoch.

    Validation is fail-closed: any non-finite float, a non-positive ``flux``, a
    negative ``sunspots``, an out-of-range ``lock_strength``, or an
    out-of-range ``observed_unix`` raises :class:`ProvenanceError` at
    construction.
    """

    flux: float
    sunspots: int
    solar_wind_kms: float
    lock_strength: float
    phase_bias_rad: float
    observed_unix: int

    def __post_init__(self) -> None:
        for name in ("flux", "solar_wind_kms", "lock_strength", "phase_bias_rad"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ProvenanceError(f"{name} must be a real number, got {value!r}")
            if not math.isfinite(float(value)):
                raise ProvenanceError(f"{name} must be finite, got {value!r}")

        if self.flux <= 0.0:
            raise ProvenanceError(f"flux must be > 0, got {self.flux!r}")
        if self.solar_wind_kms <= 0.0:
            raise ProvenanceError(
                f"solar_wind_kms must be > 0, got {self.solar_wind_kms!r}"
            )

        if isinstance(self.sunspots, bool) or not isinstance(self.sunspots, int):
            raise ProvenanceError(f"sunspots must be an int, got {self.sunspots!r}")
        if self.sunspots < 0:
            raise ProvenanceError(f"sunspots must be >= 0, got {self.sunspots!r}")
        if self.sunspots > 0x7FFFFFFF:
            raise ProvenanceError(f"sunspots exceeds int32 range: {self.sunspots!r}")

        if not (0.0 <= self.lock_strength <= 1.0):
            raise ProvenanceError(
                f"lock_strength must be in [0, 1], got {self.lock_strength!r}"
            )

        if isinstance(self.observed_unix, bool) or not isinstance(
            self.observed_unix, int
        ):
            raise ProvenanceError(
                f"observed_unix must be an int, got {self.observed_unix!r}"
            )
        if not (0 <= self.observed_unix <= 0xFFFFFFFF):
            raise ProvenanceError(
                f"observed_unix must fit uint32, got {self.observed_unix!r}"
            )


def canonical_bytes(rec: TelemetryRecord) -> bytes:
    """Pack a record into its 24-byte canonical little-endian form.

    Layout (format ``"<f i f f f I"``, no alignment padding):

    ===== ==== ======== ================
    off   size type     field
    ===== ==== ======== ================
    0     4    float32  flux
    4     4    int32    sunspots
    8     4    float32  solar_wind_kms
    12    4    float32  lock_strength
    16    4    float32  phase_bias_rad
    20    4    uint32   observed_unix
    ===== ==== ======== ================

    Floats are stored as IEEE-754 single precision (``float32``), so the value
    round-tripped through :func:`extract_lsb`/:func:`verify_payload` is the
    ``float32`` projection of the original double — this is intentional and the
    C mirror produces the identical bytes. The output is exactly
    :data:`RECORD_SIZE` bytes.
    """
    if not isinstance(rec, TelemetryRecord):
        raise ProvenanceError(
            f"canonical_bytes requires a TelemetryRecord, got {rec!r}"
        )
    return RECORD_STRUCT.pack(
        float(rec.flux),
        int(rec.sunspots),
        float(rec.solar_wind_kms),
        float(rec.lock_strength),
        float(rec.phase_bias_rad),
        int(rec.observed_unix),
    )


def _unpack_record(raw: bytes) -> TelemetryRecord:
    """Inverse of :func:`canonical_bytes`. Validates via the constructor."""
    if len(raw) != RECORD_SIZE:
        raise ProvenanceError(f"record must be {RECORD_SIZE} bytes, got {len(raw)}")
    flux, sunspots, wind, lock, phase, observed = RECORD_STRUCT.unpack(raw)
    return TelemetryRecord(
        flux=flux,
        sunspots=sunspots,
        solar_wind_kms=wind,
        lock_strength=lock,
        phase_bias_rad=phase,
        observed_unix=observed,
    )


def provenance_digest(rec: TelemetryRecord) -> str:
    """Return the lowercase hex SHA-256 of the record's canonical bytes."""
    return hashlib.sha256(canonical_bytes(rec)).hexdigest()


def short_signature(rec: TelemetryRecord) -> str:
    """Return the first 8 hex chars of :func:`provenance_digest` (on-screen ID)."""
    return provenance_digest(rec)[:8]


def signature_bits(signature: str) -> tuple[int, ...]:
    """Return the 32 visible-strip bits for an 8-hex provenance signature.

    The native HUD mirrors this by drawing one high-contrast cell for each bit of
    the first four digest bytes. The strip is redundant with the LSB payload; it
    exists only as a robust capture fallback when compositor resampling destroys
    row-0 blue LSBs.
    """
    if not isinstance(signature, str):
        raise ProvenanceError(f"signature must be a string, got {signature!r}")
    sig = signature.strip().lower()
    if len(sig) != SIGNATURE_HEX_SIZE:
        raise ProvenanceError(
            f"signature must be {SIGNATURE_HEX_SIZE} hex chars, got {len(sig)}"
        )
    try:
        raw = bytes.fromhex(sig)
    except ValueError as exc:
        raise ProvenanceError(f"signature must be lowercase hex: {signature!r}") from exc
    return tuple((byte >> (7 - bit)) & 1 for byte in raw for bit in range(8))


def build_payload(rec: TelemetryRecord) -> bytes:
    """Return the embeddable payload: canonical bytes + 4-byte SHA-256 checksum.

    The checksum is the first :data:`CHECKSUM_SIZE` bytes of the SHA-256 of the
    canonical bytes. The result is exactly :data:`PAYLOAD_SIZE` bytes.
    """
    body = canonical_bytes(rec)
    checksum = hashlib.sha256(body).digest()[:CHECKSUM_SIZE]
    return body + checksum


def _blue_capacity(width: int, height: int) -> int:
    """Number of blue-channel LSB bits available in a ``width x height`` RGBA buffer."""
    return width * height


def embed_lsb(rgba: bytearray, width: int, height: int, payload: bytes) -> None:
    """Embed a length-prefixed payload into the blue-channel LSBs, in place.

    The buffer is row-major RGBA, 4 bytes per pixel; the blue byte is at
    ``pixel_index * 4 + 2``. The bit stream written is, MSB-first per byte:

    * a :data:`LENGTH_PREFIX_SIZE`-byte (uint16) little-endian payload length,
    * followed by ``payload`` itself.

    Only the LSB of each touched blue byte is modified; R, G, A and all higher
    blue bits are left untouched. Unused trailing pixels are not modified.

    Raises:
        ProvenanceError: if ``rgba`` is not exactly ``width*height*4`` bytes,
            if dimensions are non-positive, if ``payload`` exceeds the uint16
            length prefix, or if the buffer cannot hold the bit stream.
    """
    if not isinstance(rgba, bytearray):
        raise ProvenanceError("embed_lsb requires a mutable bytearray buffer")
    if width <= 0 or height <= 0:
        raise ProvenanceError(f"width and height must be positive: {width}x{height}")
    expected = width * height * 4
    if len(rgba) != expected:
        raise ProvenanceError(
            f"buffer is {len(rgba)} bytes, expected {expected} for {width}x{height} RGBA"
        )
    if len(payload) > 0xFFFF:
        raise ProvenanceError(
            f"payload too large for uint16 length prefix: {len(payload)} bytes"
        )

    header = struct.pack("<H", len(payload))
    stream = header + payload
    total_bits = len(stream) * 8
    if total_bits > _blue_capacity(width, height):
        raise ProvenanceError(
            f"buffer holds {_blue_capacity(width, height)} blue LSBs, "
            f"need {total_bits} for {len(payload)}-byte payload"
        )

    for bit_index in range(total_bits):
        byte = stream[bit_index >> 3]
        bit = (byte >> (7 - (bit_index & 7))) & 1
        blue_pos = bit_index * 4 + 2
        rgba[blue_pos] = (rgba[blue_pos] & 0xFE) | bit


def _read_blue_bits(rgba: bytes, start_pixel: int, n_bits: int) -> bytes:
    """Read ``n_bits`` blue LSBs (MSB-first) starting at ``start_pixel`` -> bytes."""
    out = bytearray(n_bits // 8)
    for bit_index in range(n_bits):
        blue_pos = (start_pixel + bit_index) * 4 + 2
        bit = rgba[blue_pos] & 1
        if bit:
            out[bit_index >> 3] |= 1 << (7 - (bit_index & 7))
    return bytes(out)


def extract_lsb(rgba: bytes, width: int, height: int) -> bytes:
    """Recover the embedded payload from the blue-channel LSBs.

    Reads the :data:`LENGTH_PREFIX_SIZE`-byte length prefix, then that many
    payload bytes, from the blue LSBs (row-major, MSB-first per byte).

    Raises:
        ProvenanceError: on bad dimensions, a wrong-sized buffer, or a declared
            length that does not fit in the remaining buffer.
    """
    if width <= 0 or height <= 0:
        raise ProvenanceError(f"width and height must be positive: {width}x{height}")
    expected = width * height * 4
    if len(rgba) != expected:
        raise ProvenanceError(
            f"buffer is {len(rgba)} bytes, expected {expected} for {width}x{height} RGBA"
        )

    header_bits = LENGTH_PREFIX_SIZE * 8
    if header_bits > _blue_capacity(width, height):
        raise ProvenanceError("buffer too small to hold a length prefix")
    header = _read_blue_bits(rgba, 0, header_bits)
    (length,) = struct.unpack("<H", header)

    total_bits = (LENGTH_PREFIX_SIZE + length) * 8
    if total_bits > _blue_capacity(width, height):
        raise ProvenanceError(
            f"declared payload length {length} exceeds buffer capacity"
        )
    # The length prefix occupies LENGTH_PREFIX_SIZE*8 bits = that many pixels
    # (one bit per blue LSB), so the payload begins at that pixel offset.
    payload = _read_blue_bits(rgba, LENGTH_PREFIX_SIZE * 8, length * 8)
    return payload


def verify_payload(payload: bytes) -> TelemetryRecord:
    """Re-parse a payload, recompute its checksum, and return the record.

    Raises:
        ProvenanceError: if the payload is the wrong size, the recomputed
            4-byte SHA-256 checksum does not match (tamper), or the embedded
            record fails validation.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise ProvenanceError(f"payload must be bytes, got {type(payload).__name__}")
    if len(payload) != PAYLOAD_SIZE:
        raise ProvenanceError(
            f"payload must be {PAYLOAD_SIZE} bytes, got {len(payload)}"
        )

    body = bytes(payload[:RECORD_SIZE])
    stored = bytes(payload[RECORD_SIZE:])
    expected = hashlib.sha256(body).digest()[:CHECKSUM_SIZE]
    if stored != expected:
        raise ProvenanceError("checksum mismatch — payload is corrupt or tampered")
    return _unpack_record(body)
