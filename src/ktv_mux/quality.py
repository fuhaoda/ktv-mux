from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any


def analyze_wav(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()
        raw = wav.readframes(frames)
    peak, rms = _peak_and_rms(raw, sample_width)
    full_scale = float((1 << (8 * sample_width - 1)) - 1)
    return {
        "path": str(path),
        "exists": True,
        "duration": round(frames / sample_rate, 3) if sample_rate else 0,
        "channels": channels,
        "sample_rate": sample_rate,
        "sample_width": sample_width,
        "peak_dbfs": _dbfs(peak, full_scale),
        "rms_dbfs": _dbfs(rms, full_scale),
        "size_bytes": path.stat().st_size,
    }


def separation_quality_report(
    *,
    mix_wav: Path,
    instrumental_wav: Path,
    vocals_wav: Path,
) -> dict[str, Any]:
    mix = analyze_wav(mix_wav)
    instrumental = analyze_wav(instrumental_wav)
    vocals = analyze_wav(vocals_wav)
    return {
        "mix": mix,
        "instrumental": instrumental,
        "vocals": vocals,
        "instrumental_rms_delta_db": _delta(instrumental.get("rms_dbfs"), mix.get("rms_dbfs")),
        "vocals_rms_delta_db": _delta(vocals.get("rms_dbfs"), mix.get("rms_dbfs")),
    }


def _dbfs(value: int, full_scale: float) -> float | None:
    if value <= 0 or full_scale <= 0:
        return None
    return round(20.0 * math.log10(value / full_scale), 2)


def _delta(value: Any, base: Any) -> float | None:
    if value is None or base is None:
        return None
    return round(float(value) - float(base), 2)


def _peak_and_rms(raw: bytes, sample_width: int) -> tuple[int, int]:
    if not raw or sample_width <= 0:
        return 0, 0
    count = len(raw) // sample_width
    if count == 0:
        return 0, 0

    peak = 0
    total_square = 0
    for index in range(0, count * sample_width, sample_width):
        sample = _pcm_sample(raw[index : index + sample_width], sample_width)
        absolute = abs(sample)
        peak = max(peak, absolute)
        total_square += absolute * absolute
    return peak, int(math.sqrt(total_square / count))


def _pcm_sample(chunk: bytes, sample_width: int) -> int:
    if sample_width == 1:
        return chunk[0] - 128
    if sample_width == 3:
        sign_byte = b"\xff" if chunk[2] & 0x80 else b"\x00"
        return int.from_bytes(chunk + sign_byte, "little", signed=True)
    return int.from_bytes(chunk, "little", signed=True)
