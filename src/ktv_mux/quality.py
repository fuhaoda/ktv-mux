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
    clipping = _clipping_stats(raw, sample_width)
    silence = _silence_ratio(raw, sample_width, threshold_ratio=0.001)
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
        "clipped_samples": clipping["clipped_samples"],
        "clipped_ratio": clipping["clipped_ratio"],
        "silence_ratio": silence,
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
    report = {
        "mix": mix,
        "instrumental": instrumental,
        "vocals": vocals,
        "instrumental_rms_delta_db": _delta(instrumental.get("rms_dbfs"), mix.get("rms_dbfs")),
        "vocals_rms_delta_db": _delta(vocals.get("rms_dbfs"), mix.get("rms_dbfs")),
    }
    report["recommendations"] = quality_recommendations(report)
    return report


def quality_recommendations(report: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    instrumental = report.get("instrumental") or {}
    vocals = report.get("vocals") or {}
    mix = report.get("mix") or {}
    if _metric(instrumental, "clipped_ratio") > 0.001 or _metric(mix, "clipped_ratio") > 0.001:
        recommendations.append("Clipping detected. Lower the source or stem gain before muxing.")
    if _metric(instrumental, "silence_ratio") > 0.2:
        recommendations.append("Instrumental contains long silence. Check that the selected source track is correct.")
    instrumental_rms = instrumental.get("rms_dbfs")
    if instrumental_rms is not None and float(instrumental_rms) < -30:
        recommendations.append("Instrumental is very quiet. Consider normalizing or selecting another source track.")
    vocals_delta = report.get("vocals_rms_delta_db")
    instrumental_delta = report.get("instrumental_rms_delta_db")
    if vocals_delta is not None and instrumental_delta is not None and float(vocals_delta) >= float(instrumental_delta):
        recommendations.append("Vocal separation may be weak. Try another source track or Demucs model.")
    if vocals.get("exists") is False or instrumental.get("exists") is False:
        recommendations.append("One or more stem files are missing. Re-run separation before muxing.")
    if not recommendations:
        recommendations.append("No obvious level issues detected.")
    return recommendations


def _dbfs(value: int, full_scale: float) -> float | None:
    if value <= 0 or full_scale <= 0:
        return None
    return round(20.0 * math.log10(value / full_scale), 2)


def _delta(value: Any, base: Any) -> float | None:
    if value is None or base is None:
        return None
    return round(float(value) - float(base), 2)


def _metric(data: dict[str, Any], key: str) -> float:
    try:
        return float(data.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


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


def _clipping_stats(raw: bytes, sample_width: int) -> dict[str, Any]:
    if not raw or sample_width <= 0:
        return {"clipped_samples": 0, "clipped_ratio": 0.0}
    count = len(raw) // sample_width
    if count == 0:
        return {"clipped_samples": 0, "clipped_ratio": 0.0}
    max_positive = (1 << (8 * sample_width - 1)) - 1
    max_negative = -(1 << (8 * sample_width - 1))
    clipped = 0
    for index in range(0, count * sample_width, sample_width):
        sample = _pcm_sample(raw[index : index + sample_width], sample_width)
        if sample >= max_positive or sample <= max_negative:
            clipped += 1
    return {"clipped_samples": clipped, "clipped_ratio": round(clipped / count, 6)}


def _silence_ratio(raw: bytes, sample_width: int, *, threshold_ratio: float) -> float:
    if not raw or sample_width <= 0:
        return 0.0
    count = len(raw) // sample_width
    if count == 0:
        return 0.0
    full_scale = float((1 << (8 * sample_width - 1)) - 1)
    threshold = full_scale * threshold_ratio
    silent = 0
    for index in range(0, count * sample_width, sample_width):
        sample = _pcm_sample(raw[index : index + sample_width], sample_width)
        if abs(sample) <= threshold:
            silent += 1
    return round(silent / count, 6)


def _pcm_sample(chunk: bytes, sample_width: int) -> int:
    if sample_width == 1:
        return chunk[0] - 128
    if sample_width == 3:
        sign_byte = b"\xff" if chunk[2] & 0x80 else b"\x00"
        return int.from_bytes(chunk + sign_byte, "little", signed=True)
    return int.from_bytes(chunk, "little", signed=True)
