from __future__ import annotations

from typing import Any

RECIPE_STAGES: dict[str, list[str]] = {
    "instrumental-review": ["probe", "preview-tracks", "separate-sample"],
    "full-instrumental": ["probe", "extract", "separate"],
    "replace-track2": ["probe", "extract", "separate", "replace-audio"],
    "final-ktv": ["probe", "extract", "separate", "align", "mux"],
}

RECIPE_LABELS = {
    "instrumental-review": "Preview tracks and make a short instrumental sample.",
    "full-instrumental": "Create a full instrumental WAV for listening.",
    "replace-track2": "Generate an instrumental and build an audio-replaced MKV.",
    "final-ktv": "Run the full KTV MKV workflow.",
}


def recipe_plan(recipe: str, *, song_ids: list[str]) -> dict[str, Any]:
    if recipe not in RECIPE_STAGES:
        raise ValueError(f"unsupported recipe: {recipe}")
    return {
        "recipe": recipe,
        "label": RECIPE_LABELS[recipe],
        "stages": RECIPE_STAGES[recipe],
        "songs": [{"song_id": song_id, "stages": RECIPE_STAGES[recipe]} for song_id in song_ids],
    }
