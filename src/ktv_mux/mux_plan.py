from __future__ import annotations

from typing import Any

from .preflight import preflight_from_summary
from .track_roles import track_role_report


def ktv_mux_plan(
    summary: dict[str, Any],
    report: dict[str, Any],
    *,
    audio_order: str = "instrumental-first",
) -> dict[str, Any]:
    preflight = preflight_from_summary(summary, report)
    if audio_order == "original-first":
        audio = [
            {"track": 1, "source": "mix.wav", "title": "原唱", "default": False},
            {"track": 2, "source": "instrumental.wav", "title": "伴奏", "default": True},
        ]
    else:
        audio = [
            {"track": 1, "source": "instrumental.wav", "title": "伴奏", "default": True},
            {"track": 2, "source": "mix.wav", "title": "原唱", "default": False},
        ]
    return {
        "kind": "ktv-mkv",
        "ready": bool(preflight["ok_for_final_mkv"]),
        "audio_order": audio_order,
        "video": "source video stream 1",
        "audio": audio,
        "subtitles": [{"track": 1, "source": "lyrics.ass", "title": "歌词", "default": True}],
        "warnings": list(preflight["warnings"]),
    }


def replace_audio_plan(
    summary: dict[str, Any],
    report: dict[str, Any],
    *,
    keep_audio_index: int = 0,
    copy_subtitles: bool = True,
) -> dict[str, Any]:
    preflight = preflight_from_summary(summary, report)
    probe = (report or {}).get("probe") or {}
    audio_streams = [s for s in probe.get("streams") or [] if s.get("codec_type") == "audio"]
    kept_role = (
        track_role_report(report, keep_audio_index, audio_streams[keep_audio_index])
        if 0 <= keep_audio_index < len(audio_streams)
        else {"role": "unknown", "label": "Unknown"}
    )
    subtitles = [{"source": "source subtitles", "mode": "copy"}] if copy_subtitles else []
    return {
        "kind": "audio-replaced-mkv",
        "ready": bool(preflight["ok_for_replace_audio"]),
        "video": "source video stream 1",
        "audio": [
            {
                "track": 1,
                "source": f"source Track {keep_audio_index + 1}",
                "title": "原唱",
                "default": True,
                "role": kept_role["role"],
            },
            {"track": 2, "source": "instrumental.wav", "title": "伴奏", "default": False, "role": "instrumental"},
        ],
        "subtitles": subtitles,
        "warnings": list(preflight["warnings"]),
    }
