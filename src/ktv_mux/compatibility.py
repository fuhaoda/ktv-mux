from __future__ import annotations

from typing import Any

PLAYER_MATRIX: list[dict[str, str]] = [
    {
        "player": "VLC",
        "platform": "macOS / Windows",
        "expected": "Good",
        "notes": "MKV, dual audio, and ASS subtitles are normally supported.",
    },
    {
        "player": "IINA",
        "platform": "macOS",
        "expected": "Good",
        "notes": "Recommended local macOS player for ASS karaoke subtitles.",
    },
    {
        "player": "Infuse",
        "platform": "Apple TV / iOS / macOS",
        "expected": "Good",
        "notes": "Usually handles MKV and selectable audio; check ASS styling on target device.",
    },
    {
        "player": "QuickTime Player",
        "platform": "macOS",
        "expected": "Limited",
        "notes": "Native QuickTime support for MKV and ASS subtitles is limited.",
    },
    {
        "player": "Windows Media Player",
        "platform": "Windows",
        "expected": "Limited",
        "notes": "MKV may play, but ASS subtitle and track selection support varies by system codecs.",
    },
]


def compatibility_report(audit: dict[str, Any] | None = None) -> dict[str, Any]:
    audit = audit or {}
    warnings: list[str] = []
    if audit and not audit.get("ok"):
        warnings.append("Output stream audit has warnings; player compatibility should be verified manually.")
    if audit and int(audit.get("audio_streams") or 0) < 2:
        warnings.append("Only one audio stream was detected; karaoke track switching will not be available.")
    if audit and int(audit.get("subtitle_streams") or 0) < 1:
        warnings.append("No subtitle stream was detected; lyric display depends on external files.")
    return {"matrix": PLAYER_MATRIX, "warnings": warnings, "recommended_player": "IINA on macOS or VLC on any desktop OS"}
