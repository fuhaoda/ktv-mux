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
        "duration_delta_seconds": _duration_delta(mix, instrumental, vocals),
        "sample_rate_match": _same_metric("sample_rate", mix, instrumental, vocals),
        "channel_match": _same_metric("channels", mix, instrumental, vocals),
    }
    report["vocal_bleed_risk"] = vocal_bleed_risk(report)
    report["recommendations"] = quality_recommendations(report)
    report["recommendations_zh"] = quality_recommendations_zh(report)
    return report


def mkv_audit_report(
    info: dict[str, Any],
    *,
    expected_audio_streams: int = 2,
    expected_subtitle_streams: int = 1,
) -> dict[str, Any]:
    video = info.get("video_streams") or []
    audio = info.get("audio_streams") or []
    subtitles = info.get("subtitle_streams") or []
    warnings: list[str] = []
    if not video:
        warnings.append("No video stream found in output MKV.")
    if len(audio) < expected_audio_streams:
        warnings.append(f"Expected at least {expected_audio_streams} audio streams, found {len(audio)}.")
    if len(subtitles) < expected_subtitle_streams:
        warnings.append(f"Expected at least {expected_subtitle_streams} subtitle streams, found {len(subtitles)}.")
    if audio and not any((stream.get("disposition") or {}).get("default") for stream in audio):
        warnings.append("No default audio stream is marked.")
    if subtitles and not any((stream.get("disposition") or {}).get("default") for stream in subtitles):
        warnings.append("No default subtitle stream is marked.")
    return {
        "ok": not warnings,
        "duration": info.get("duration"),
        "video_streams": len(video),
        "audio_streams": len(audio),
        "subtitle_streams": len(subtitles),
        "audio_titles": [(stream.get("tags") or {}).get("title") for stream in audio],
        "subtitle_titles": [(stream.get("tags") or {}).get("title") for stream in subtitles],
        "default_audio_indexes": [
            index for index, stream in enumerate(audio) if (stream.get("disposition") or {}).get("default")
        ],
        "default_subtitle_indexes": [
            index for index, stream in enumerate(subtitles) if (stream.get("disposition") or {}).get("default")
        ],
        "warnings": warnings,
    }


def quality_recommendations(report: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    instrumental = report.get("instrumental") or {}
    vocals = report.get("vocals") or {}
    mix = report.get("mix") or {}
    if _metric(instrumental, "clipped_ratio") > 0.001 or _metric(mix, "clipped_ratio") > 0.001:
        recommendations.append("Clipping detected. Lower the source or stem gain before muxing.")
    if _metric(vocals, "clipped_ratio") > 0.001:
        recommendations.append("Vocal stem clipping detected. Re-run separation or normalize before review.")
    if report.get("duration_delta_seconds") is not None and float(report["duration_delta_seconds"]) > 0.5:
        recommendations.append("Stem duration does not match the source mix. Re-run extract and separation.")
    if report.get("sample_rate_match") is False:
        recommendations.append("Stem sample rates differ. Re-render WAV files before muxing.")
    if report.get("channel_match") is False:
        recommendations.append("Stem channel layouts differ. Re-render WAV files before muxing.")
    if _metric(instrumental, "silence_ratio") > 0.2:
        recommendations.append("Instrumental contains long silence. Check that the selected source track is correct.")
    instrumental_rms = instrumental.get("rms_dbfs")
    if instrumental_rms is not None and float(instrumental_rms) < -30:
        recommendations.append("Instrumental is very quiet. Consider normalizing or selecting another source track.")
    vocals_delta = report.get("vocals_rms_delta_db")
    instrumental_delta = report.get("instrumental_rms_delta_db")
    if vocals_delta is not None and instrumental_delta is not None and float(vocals_delta) >= float(instrumental_delta):
        recommendations.append("Vocal separation may be weak. Try another source track or Demucs model.")
    if report.get("vocal_bleed_risk") == "high":
        recommendations.append("High residual vocal risk. Review a chorus section before replacing Track 2.")
    if vocals.get("exists") is False or instrumental.get("exists") is False:
        recommendations.append("One or more stem files are missing. Re-run separation before muxing.")
    if not recommendations:
        recommendations.append("No obvious level issues detected.")
    return recommendations


def quality_recommendations_zh(report: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    instrumental = report.get("instrumental") or {}
    vocals = report.get("vocals") or {}
    mix = report.get("mix") or {}
    if _metric(instrumental, "clipped_ratio") > 0.001 or _metric(mix, "clipped_ratio") > 0.001:
        recommendations.append("检测到爆音；封装前建议降低源音频或伴奏增益。")
    if _metric(vocals, "clipped_ratio") > 0.001:
        recommendations.append("人声轨有爆音；建议重新分离或先做响度归一化。")
    if report.get("duration_delta_seconds") is not None and float(report["duration_delta_seconds"]) > 0.5:
        recommendations.append("分离后的音频时长和原混不一致；建议重新抽音频并重新分离。")
    if report.get("sample_rate_match") is False:
        recommendations.append("音频采样率不一致；建议重新渲染 WAV 后再封装。")
    if report.get("channel_match") is False:
        recommendations.append("声道布局不一致；建议重新渲染 WAV 后再封装。")
    if _metric(instrumental, "silence_ratio") > 0.2:
        recommendations.append("伴奏里有较长静音；请确认选择的是正确的源音轨。")
    instrumental_rms = instrumental.get("rms_dbfs")
    if instrumental_rms is not None and float(instrumental_rms) < -30:
        recommendations.append("伴奏音量偏小；可以归一化或换一个源音轨。")
    vocals_delta = report.get("vocals_rms_delta_db")
    instrumental_delta = report.get("instrumental_rms_delta_db")
    if vocals_delta is not None and instrumental_delta is not None and float(vocals_delta) >= float(instrumental_delta):
        recommendations.append("人声去除效果可能偏弱；建议尝试另一个源音轨或 Demucs 模型。")
    if report.get("vocal_bleed_risk") == "high":
        recommendations.append("残留人声风险较高；建议先试听副歌片段，再决定是否替换第 2 轨。")
    if vocals.get("exists") is False or instrumental.get("exists") is False:
        recommendations.append("缺少伴奏或人声 stem；请先重新运行分离。")
    if not recommendations:
        recommendations.append("没有发现明显电平问题；建议用播放器试听最终效果。")
    return recommendations


def vocal_bleed_risk(report: dict[str, Any]) -> str:
    vocals_delta = report.get("vocals_rms_delta_db")
    instrumental_delta = report.get("instrumental_rms_delta_db")
    if vocals_delta is None or instrumental_delta is None:
        return "unknown"
    gap = float(instrumental_delta) - float(vocals_delta)
    if gap < 1.0:
        return "high"
    if gap < 4.0:
        return "medium"
    return "low"


def _dbfs(value: int, full_scale: float) -> float | None:
    if value <= 0 or full_scale <= 0:
        return None
    return round(20.0 * math.log10(value / full_scale), 2)


def _delta(value: Any, base: Any) -> float | None:
    if value is None or base is None:
        return None
    return round(float(value) - float(base), 2)


def _duration_delta(*items: dict[str, Any]) -> float | None:
    durations = [float(item["duration"]) for item in items if item.get("duration") is not None]
    if len(durations) < 2:
        return None
    return round(max(durations) - min(durations), 3)


def _same_metric(key: str, *items: dict[str, Any]) -> bool | None:
    values = [item.get(key) for item in items if item.get(key) is not None]
    if len(values) < 2:
        return None
    return len(set(values)) == 1


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
