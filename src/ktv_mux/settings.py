from __future__ import annotations

from typing import Any

from .jsonio import read_json, write_json
from .paths import LibraryPaths

DEFAULT_SETTINGS: dict[str, Any] = {
    "worker_count": 2,
    "preview_start": 0.0,
    "preview_duration": 20.0,
    "preview_count": 1,
    "preview_spacing": 45.0,
    "preview_preset": "manual",
    "demucs_model": "htdemucs",
    "demucs_device": "auto",
    "normalize_target_i": -16.0,
    "auto_refresh_seconds": 3,
    "default_audio_order": "instrumental-first",
    "default_duration_limit": 0.0,
    "output_template": "{song_id}.ktv.mkv",
    "package_include_logs": False,
    "subtitle_font_size": 48,
    "subtitle_margin_v": 58,
    "subtitle_primary_colour": "&H00FFFFFF",
    "subtitle_secondary_colour": "&H0000D7FF",
    "instrumental_track_title": "伴奏",
    "original_track_title": "原唱",
}


def load_settings(library: LibraryPaths) -> dict[str, Any]:
    data = read_json(library.settings_json(), default={}) or {}
    settings = {**DEFAULT_SETTINGS, **data}
    settings["worker_count"] = max(1, int(settings.get("worker_count") or DEFAULT_SETTINGS["worker_count"]))
    settings["preview_start"] = max(0.0, float(settings.get("preview_start") or 0.0))
    settings["preview_duration"] = max(1.0, float(settings.get("preview_duration") or DEFAULT_SETTINGS["preview_duration"]))
    settings["preview_count"] = max(1, int(settings.get("preview_count") or DEFAULT_SETTINGS["preview_count"]))
    settings["preview_spacing"] = max(1.0, float(settings.get("preview_spacing") or DEFAULT_SETTINGS["preview_spacing"]))
    settings["preview_preset"] = str(settings.get("preview_preset") or DEFAULT_SETTINGS["preview_preset"])
    settings["demucs_model"] = str(settings.get("demucs_model") or DEFAULT_SETTINGS["demucs_model"])
    settings["demucs_device"] = str(settings.get("demucs_device") or DEFAULT_SETTINGS["demucs_device"])
    settings["normalize_target_i"] = float(settings.get("normalize_target_i") or DEFAULT_SETTINGS["normalize_target_i"])
    settings["auto_refresh_seconds"] = max(1, int(settings.get("auto_refresh_seconds") or DEFAULT_SETTINGS["auto_refresh_seconds"]))
    settings["default_audio_order"] = _choice(
        settings.get("default_audio_order"),
        {"instrumental-first", "original-first"},
        DEFAULT_SETTINGS["default_audio_order"],
    )
    settings["default_duration_limit"] = max(0.0, float(settings.get("default_duration_limit") or 0.0))
    settings["output_template"] = str(settings.get("output_template") or DEFAULT_SETTINGS["output_template"])
    settings["package_include_logs"] = bool(settings.get("package_include_logs", DEFAULT_SETTINGS["package_include_logs"]))
    settings["subtitle_font_size"] = max(20, min(96, int(settings.get("subtitle_font_size") or 48)))
    settings["subtitle_margin_v"] = max(10, min(180, int(settings.get("subtitle_margin_v") or 58)))
    settings["subtitle_primary_colour"] = _ass_colour(settings.get("subtitle_primary_colour"), "&H00FFFFFF")
    settings["subtitle_secondary_colour"] = _ass_colour(settings.get("subtitle_secondary_colour"), "&H0000D7FF")
    settings["instrumental_track_title"] = str(
        settings.get("instrumental_track_title") or DEFAULT_SETTINGS["instrumental_track_title"]
    )
    settings["original_track_title"] = str(settings.get("original_track_title") or DEFAULT_SETTINGS["original_track_title"])
    return settings


def save_settings(library: LibraryPaths, values: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings(library)
    settings.update({key: value for key, value in values.items() if value is not None})
    settings["worker_count"] = max(1, int(settings["worker_count"]))
    settings["preview_start"] = max(0.0, float(settings["preview_start"]))
    settings["preview_duration"] = max(1.0, float(settings["preview_duration"]))
    settings["preview_count"] = max(1, int(settings["preview_count"]))
    settings["preview_spacing"] = max(1.0, float(settings["preview_spacing"]))
    settings["preview_preset"] = str(settings["preview_preset"])
    settings["demucs_model"] = str(settings["demucs_model"])
    settings["demucs_device"] = str(settings["demucs_device"])
    settings["normalize_target_i"] = float(settings["normalize_target_i"])
    settings["auto_refresh_seconds"] = max(1, int(settings["auto_refresh_seconds"]))
    settings["default_audio_order"] = _choice(
        settings["default_audio_order"],
        {"instrumental-first", "original-first"},
        DEFAULT_SETTINGS["default_audio_order"],
    )
    settings["default_duration_limit"] = max(0.0, float(settings["default_duration_limit"]))
    settings["output_template"] = str(settings["output_template"])
    settings["package_include_logs"] = bool(settings["package_include_logs"])
    settings["subtitle_font_size"] = max(20, min(96, int(settings["subtitle_font_size"])))
    settings["subtitle_margin_v"] = max(10, min(180, int(settings["subtitle_margin_v"])))
    settings["subtitle_primary_colour"] = _ass_colour(settings["subtitle_primary_colour"], "&H00FFFFFF")
    settings["subtitle_secondary_colour"] = _ass_colour(settings["subtitle_secondary_colour"], "&H0000D7FF")
    settings["instrumental_track_title"] = str(settings["instrumental_track_title"])
    settings["original_track_title"] = str(settings["original_track_title"])
    write_json(library.settings_json(), settings)
    return settings


def _choice(value: Any, choices: set[str], fallback: str) -> str:
    parsed = str(value or fallback)
    return parsed if parsed in choices else fallback


def _ass_colour(value: Any, fallback: str) -> str:
    parsed = str(value or fallback).strip()
    if parsed.startswith("&H") and len(parsed) == 10:
        return parsed
    return fallback
