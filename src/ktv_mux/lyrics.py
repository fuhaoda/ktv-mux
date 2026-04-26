from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_LRC_TIMESTAMP_RE = re.compile(r"\[(?:\d{1,2}:)?\d{1,2}:\d{1,2}(?:[.:]\d{1,3})?\]")
_LRC_TIMESTAMP_VALUE_RE = re.compile(r"\[((?:\d{1,2}:)?\d{1,2}:\d{1,2}(?:[.:]\d{1,3})?)\]")
_LRC_TIME_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?$")
_CHORD_RE = re.compile(r"\[[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\d*(?:/[A-G](?:#|b)?)?\]")
_SPACE_RE = re.compile(r"\s+")
_SRT_TIME_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)
_ASS_OVERRIDE_RE = re.compile(r"\{[^}]*\}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


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


def timed_text_to_alignment(text: str, suffix: str) -> dict[str, Any] | None:
    suffix = suffix.lower()
    if suffix == ".srt":
        return srt_text_to_alignment(text)
    if suffix == ".ass":
        return ass_text_to_alignment(text)
    return None


def alignment_to_plain_text(alignment: dict[str, Any]) -> str:
    return "\n".join(str(line.get("text") or "") for line in alignment.get("lines") or [] if line.get("text"))


def srt_text_to_alignment(text: str) -> dict[str, Any]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines: list[dict[str, Any]] = []
    for block in blocks:
        raw_lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not raw_lines:
            continue
        time_index = next((index for index, line in enumerate(raw_lines) if _SRT_TIME_RE.search(line)), None)
        if time_index is None:
            continue
        match = _SRT_TIME_RE.search(raw_lines[time_index])
        if not match:
            continue
        lyric = clean_lyrics_line(" ".join(raw_lines[time_index + 1 :]))
        if not lyric:
            continue
        start = _subtitle_seconds(match.group("start"))
        end = max(start + 0.2, _subtitle_seconds(match.group("end")))
        lines.append({"text": lyric, "start": start, "end": end, "tokens": _tokens_for_window(lyric, start, end)})
    return {"backend": "srt", "warning": None, "lines": lines}


def ass_text_to_alignment(text: str) -> dict[str, Any]:
    fields: list[str] = []
    lines: list[dict[str, Any]] = []
    in_events = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower() == "[events]":
            in_events = True
            continue
        if line.startswith("[") and line.endswith("]") and line.lower() != "[events]":
            in_events = False
            continue
        if not in_events:
            continue
        if line.lower().startswith("format:"):
            fields = [item.strip().lower() for item in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("dialogue:") or not fields:
            continue
        values = line.split(":", 1)[1].lstrip().split(",", max(0, len(fields) - 1))
        if len(values) != len(fields):
            continue
        row = {field: values[index].strip() for index, field in enumerate(fields)}
        lyric = clean_lyrics_line(_strip_ass_text(row.get("text", "")))
        if not lyric:
            continue
        start = _ass_seconds(row.get("start", "0:00:00.00"))
        end = max(start + 0.2, _ass_seconds(row.get("end", "0:00:00.20")))
        lines.append({"text": lyric, "start": start, "end": end, "tokens": _tokens_for_window(lyric, start, end)})
    return {"backend": "ass", "warning": None, "lines": lines}


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


def _subtitle_seconds(value: str) -> float:
    hours, minutes, rest = value.replace(",", ".").split(":")
    return round(int(hours) * 3600 + int(minutes) * 60 + float(rest), 3)


def _ass_seconds(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) != 3:
        return 0.0
    hours, minutes, seconds = parts
    return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3)


def _strip_ass_text(value: str) -> str:
    text = value.replace(r"\N", " ").replace(r"\n", " ")
    text = _ASS_OVERRIDE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    return text


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
