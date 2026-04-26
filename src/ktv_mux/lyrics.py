from __future__ import annotations

from pathlib import Path


def parse_lyrics_text(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lines.append(line)
    return lines


def parse_lyrics_file(path: Path) -> list[str]:
    return parse_lyrics_text(path.read_text(encoding="utf-8"))


def split_tokens(text: str) -> list[str]:
    if " " in text.strip():
        return [part for part in text.split(" ") if part]
    return [char for char in text if not char.isspace()]

