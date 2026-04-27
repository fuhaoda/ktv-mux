from __future__ import annotations

from typing import Any

from .errors import KtvError
from .jsonio import read_json
from .models import update_report
from .paths import LibraryPaths, normalize_song_id

TRACK_ROLES = ["unknown", "guide-vocal", "instrumental", "duet", "commentary"]

ROLE_LABELS = {
    "unknown": "Unknown",
    "guide-vocal": "Guide / Original Vocal",
    "instrumental": "Instrumental / Accompaniment",
    "duet": "Duet / Alternate Vocal",
    "commentary": "Commentary / Other",
}

ROLE_HINTS = {
    "unknown": "No role chosen yet. Listen to previews before replacing audio.",
    "guide-vocal": "Keep this as the guide/original vocal track in replacement MKVs.",
    "instrumental": "Likely accompaniment; may already be a karaoke backing track.",
    "duet": "May include a second vocal or guide vocal. Review before using for separation.",
    "commentary": "Usually not useful for KTV output.",
}


def set_track_role(
    library: LibraryPaths,
    song_id: str,
    *,
    audio_index: int,
    role: str,
    note: str = "",
) -> dict[str, Any]:
    clean_id = normalize_song_id(song_id)
    if audio_index < 0:
        raise KtvError("audio_index must be 0 or greater")
    clean_role = normalize_role(role)
    report = read_json(library.report_json(clean_id), default={}) or {}
    roles = dict(report.get("track_roles") or {})
    roles[str(audio_index)] = {
        "role": clean_role,
        "note": note.strip(),
        "source": "manual",
        "track": audio_index + 1,
    }
    update_report(library.report_json(clean_id), track_roles=roles)
    return roles[str(audio_index)]


def normalize_role(role: str) -> str:
    value = (role or "unknown").strip().lower()
    if value not in TRACK_ROLES:
        raise KtvError(f"unsupported track role: {role}")
    return value


def role_options(selected_role: str) -> list[dict[str, str | bool]]:
    selected = normalize_role(selected_role) if selected_role else "unknown"
    return [
        {
            "value": role,
            "label": ROLE_LABELS[role],
            "hint": ROLE_HINTS[role],
            "selected": role == selected,
        }
        for role in TRACK_ROLES
    ]


def track_role_report(report: dict[str, Any], audio_index: int, stream: dict[str, Any]) -> dict[str, Any]:
    roles = report.get("track_roles") or {}
    manual = roles.get(str(audio_index)) if isinstance(roles, dict) else None
    if isinstance(manual, dict) and manual.get("role"):
        role = normalize_role(str(manual.get("role")))
        return {
            "role": role,
            "label": ROLE_LABELS[role],
            "hint": manual.get("note") or ROLE_HINTS[role],
            "source": "manual",
            "track": audio_index + 1,
            "note": manual.get("note") or "",
        }
    inferred = infer_track_role(audio_index, stream)
    role = str(inferred["role"])
    return {
        "role": role,
        "label": ROLE_LABELS[role],
        "hint": inferred["hint"],
        "source": "inferred",
        "track": audio_index + 1,
        "note": "",
    }


def infer_track_role(audio_index: int, stream: dict[str, Any]) -> dict[str, str]:
    tags = stream.get("tags") or {}
    text = " ".join(str(tags.get(key) or "") for key in ["title", "handler_name", "language"]).lower()
    if any(token in text for token in ["伴奏", "karaoke", "instrumental", "accompaniment", "no vocal", "no_vocal"]):
        return {"role": "instrumental", "hint": "Track metadata looks like accompaniment."}
    if any(token in text for token in ["原唱", "vocal", "guide", "voice", "唱"]):
        return {"role": "guide-vocal", "hint": "Track metadata looks like a guide/original vocal."}
    if (stream.get("disposition") or {}).get("default"):
        return {"role": "guide-vocal", "hint": "Default source track; often the original/guide mix."}
    if audio_index == 1:
        return {"role": "instrumental", "hint": "Second KTV track is often accompaniment; confirm by preview."}
    return {"role": "unknown", "hint": "No reliable role signal; confirm by listening."}


def summarize_track_roles(report: dict[str, Any]) -> list[dict[str, Any]]:
    streams = [s for s in (((report or {}).get("probe") or {}).get("streams") or []) if s.get("codec_type") == "audio"]
    return [track_role_report(report, index, stream) for index, stream in enumerate(streams)]
