from __future__ import annotations

from typing import Any

from .jsonio import read_json
from .library import song_summary
from .paths import LibraryPaths


def song_preflight(library: LibraryPaths, song_id: str) -> dict[str, Any]:
    summary = song_summary(library, song_id)
    report = read_json(library.report_json(song_id), default={}) or {}
    return preflight_from_summary(summary, report)


def preflight_from_summary(summary: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    items = [
        _item("source", "Source video", bool(summary.get("has_source")), "Required for every workflow."),
        _item("probe", "Probe report", bool((report or {}).get("probe")), "Run Read Tracks before choosing audio."),
        _item("track_previews", "Track previews", bool((report or {}).get("track_previews")), "Recommended before separation."),
        _item("mix", "Extracted mix.wav", bool(summary.get("has_mix")), "Required for Demucs and full KTV MKV."),
        _item("instrumental", "Instrumental", bool(summary.get("has_instrumental")), "Required for replace-audio and final MKV."),
        _item(
            "instrumental_sample",
            "Sample instrumental",
            bool(summary.get("has_instrumental_sample")),
            "Recommended before full separation.",
        ),
        _item("lyrics", "Lyrics text", bool(summary.get("has_lyrics")), "Required before ASS generation."),
        _item("ass", "Karaoke ASS", bool(summary.get("has_ass")), "Required for full KTV MKV."),
        _item(
            "audio_replaced_mkv",
            "Audio-replaced MKV",
            bool(summary.get("has_audio_replaced_mkv")),
            "Useful when only Track 2 is bad.",
        ),
        _item("final_mkv", "Final KTV MKV", bool(summary.get("has_mkv")), "Final deliverable."),
    ]
    warnings = _collect_warnings(report)
    ready = {item["key"]: item["ready"] for item in items}
    return {
        "ok_for_sample_review": bool(ready["source"] and ready["instrumental_sample"]),
        "ok_for_instrumental_review": bool(ready["source"] and ready["instrumental"]),
        "ok_for_replace_audio": bool(ready["source"] and ready["instrumental"]),
        "ok_for_final_mkv": bool(ready["source"] and ready["mix"] and ready["instrumental"] and ready["ass"]),
        "items": items,
        "warnings": warnings,
    }


def _item(key: str, label: str, ready: bool, hint: str) -> dict[str, Any]:
    return {"key": key, "label": label, "ready": ready, "hint": hint}


def _collect_warnings(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in ["quality", "separation_sample_quality", "external_instrumental_fit", "final_mkv_audit", "audio_replaced_mkv_audit"]:
        data = report.get(key) if isinstance(report, dict) else None
        if isinstance(data, dict):
            warnings.extend(str(item) for item in data.get("warnings") or [] if _looks_actionable(item))
            warnings.extend(str(item) for item in data.get("recommendations_zh") or [] if _looks_actionable(item))
    return list(dict.fromkeys(warnings))


def _looks_actionable(value: Any) -> bool:
    text = str(value).strip()
    if not text:
        return False
    non_blocking = [
        "No obvious level issues detected",
        "没有发现明显电平问题",
        "可以继续试听或封装",
        "已转成 WAV",
    ]
    return not any(marker in text for marker in non_blocking)
