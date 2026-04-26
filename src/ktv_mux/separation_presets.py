from __future__ import annotations

from typing import Any

from .errors import KtvError

PRESETS: dict[str, dict[str, Any]] = {
    "fast-review": {
        "label": "Fast review",
        "label_zh": "快速试听",
        "model": "htdemucs",
        "device": "auto",
        "description": "Short feedback loop for checking whether the selected track is worth a full run.",
    },
    "balanced": {
        "label": "Balanced",
        "label_zh": "平衡质量",
        "model": "htdemucs",
        "device": "auto",
        "description": "Default Demucs two-stem run for most karaoke sources.",
    },
    "clean-vocal": {
        "label": "Cleaner vocal removal",
        "label_zh": "更干净人声",
        "model": "htdemucs",
        "device": "auto",
        "description": "Same stable model, but recorded separately so you can compare takes intentionally.",
    },
    "quality": {
        "label": "Quality",
        "label_zh": "质量优先",
        "model": "htdemucs_ft",
        "device": "auto",
        "description": "Higher quality fine-tuned model when available; falls back through normal Demucs errors.",
    },
}


def preset_options() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in PRESETS.items()]


def resolve_separation_preset(
    preset: str | None,
    *,
    model: str | None = None,
    device: str | None = None,
) -> dict[str, Any]:
    preset_id = str(preset or "balanced")
    if preset_id not in PRESETS:
        raise KtvError(f"unsupported separation preset: {preset_id}")
    resolved = {"id": preset_id, **PRESETS[preset_id]}
    if model:
        resolved["model"] = model
    if device not in {None, ""}:
        resolved["device"] = device
    return resolved
