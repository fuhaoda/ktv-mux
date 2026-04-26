from __future__ import annotations

import re
from pathlib import Path

_LRC_TIMESTAMP_RE = re.compile(r"\[(?:\d{1,2}:)?\d{1,2}:\d{1,2}(?:[.:]\d{1,3})?\]")
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


def parse_lyrics_file(path: Path) -> list[str]:
    return parse_lyrics_text(path.read_text(encoding="utf-8"))


def split_tokens(text: str) -> list[str]:
    if " " in text.strip():
        return [part for part in text.split(" ") if part]
    return [char for char in text if not char.isspace()]
