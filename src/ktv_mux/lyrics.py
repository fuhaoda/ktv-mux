from __future__ import annotations

import re
from pathlib import Path

_LRC_TIMESTAMP_RE = re.compile(r"\[(?:\d{1,2}:)?\d{1,2}:\d{1,2}(?:[.:]\d{1,3})?\]")
_LRC_TIMESTAMP_VALUE_RE = re.compile(r"\[((?:\d{1,2}:)?\d{1,2}:\d{1,2}(?:[.:]\d{1,3})?)\]")
_LRC_TIME_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?$")
_CHORD_RE = re.compile(r"\[[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\d*(?:/[A-G](?:#|b)?)?\]")
_SPACE_RE = re.compile(r"\s+")


def parse_lyrics_text(text: str) -> list[str]:
    return [line for line in normalize_lyrics_text(text).splitlines() if line]


def normalize_lyrics_text(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = clean_lyrics_line(raw)
        if not line:
            continue
        lines.append(line)
    return "\n".join(lines)


def clean_lyrics_line(raw: str) -> str:
    line = raw.strip().replace("\ufeff", "")
    line = _LRC_TIMESTAMP_RE.sub("", line)
    line = _CHORD_RE.sub("", line)
    line = line.replace("　", " ")
    line = _SPACE_RE.sub(" ", line).strip()
    return line


def parse_lrc_text(text: str) -> list[str]:
    return [line for line in normalize_lyrics_text(text).splitlines() if line]


def extract_lrc_entries(text: str) -> list[dict[str, float | str]]:
    entries: list[dict[str, float | str]] = []
    for raw in text.splitlines():
        matches = list(_LRC_TIMESTAMP_VALUE_RE.finditer(raw))
        if not matches:
            continue
        lyric = clean_lyrics_line(raw)
        if not lyric:
            continue
        for match in matches:
            entries.append({"start": _lrc_seconds(match.group(1)), "text": lyric})
    entries.sort(key=lambda entry: (float(entry["start"]), str(entry["text"])))
    return entries


def lrc_text_to_alignment(text: str) -> dict[str, object]:
    entries = extract_lrc_entries(text)
    lines = []
    for index, entry in enumerate(entries):
        start = float(entry["start"])
        next_start = float(entries[index + 1]["start"]) if index + 1 < len(entries) else start + 3.0
        end = next_start if next_start > start else start + 3.0
        lyric = str(entry["text"])
        lines.append(
            {
                "text": lyric,
                "start": round(start, 3),
                "end": round(end, 3),
                "tokens": _tokens_for_window(lyric, start, end),
            }
        )
    return {"backend": "lrc", "warning": None, "lines": lines}


def parse_lyrics_file(path: Path) -> list[str]:
    return parse_lyrics_text(path.read_text(encoding="utf-8"))


def split_tokens(text: str) -> list[str]:
    if " " in text.strip():
        return [part for part in text.split(" ") if part]
    return [char for char in text if not char.isspace()]


def _lrc_seconds(value: str) -> float:
    match = _LRC_TIME_RE.match(value)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    fraction = match.group(4) or "0"
    millis = int(fraction.ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def _tokens_for_window(text: str, start: float, end: float) -> list[dict[str, float | str]]:
    tokens = split_tokens(text) or [text]
    duration = max(0.05, end - start)
    step = duration / len(tokens)
    return [
        {
            "text": token,
            "start": round(start + step * index, 3),
            "end": round(start + step * (index + 1), 3),
        }
        for index, token in enumerate(tokens)
    ]
