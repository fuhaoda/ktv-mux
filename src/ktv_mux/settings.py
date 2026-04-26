from __future__ import annotations

from typing import Any

from .jsonio import read_json, write_json
from .paths import LibraryPaths

DEFAULT_SETTINGS: dict[str, Any] = {
    "worker_count": 2,
    "preview_start": 0.0,
    "preview_duration": 20.0,
    "auto_refresh_seconds": 3,
}


def load_settings(library: LibraryPaths) -> dict[str, Any]:
    data = read_json(library.settings_json(), default={}) or {}
    settings = {**DEFAULT_SETTINGS, **data}
    settings["worker_count"] = max(1, int(settings.get("worker_count") or DEFAULT_SETTINGS["worker_count"]))
    settings["preview_start"] = max(0.0, float(settings.get("preview_start") or 0.0))
    settings["preview_duration"] = max(1.0, float(settings.get("preview_duration") or DEFAULT_SETTINGS["preview_duration"]))
    settings["auto_refresh_seconds"] = max(1, int(settings.get("auto_refresh_seconds") or DEFAULT_SETTINGS["auto_refresh_seconds"]))
    return settings


def save_settings(library: LibraryPaths, values: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings(library)
    settings.update({key: value for key, value in values.items() if value is not None})
    settings["worker_count"] = max(1, int(settings["worker_count"]))
    settings["preview_start"] = max(0.0, float(settings["preview_start"]))
    settings["preview_duration"] = max(1.0, float(settings["preview_duration"]))
    settings["auto_refresh_seconds"] = max(1, int(settings["auto_refresh_seconds"]))
    write_json(library.settings_json(), settings)
    return settings
