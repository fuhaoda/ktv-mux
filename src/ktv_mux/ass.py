from __future__ import annotations

from typing import Any


def seconds_to_ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_centis = int(round(seconds * 100))
    centis = total_centis % 100
    total_seconds = total_centis // 100
    sec = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours}:{minutes:02d}:{sec:02d}.{centis:02d}"


def ass_karaoke_text(tokens: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for token in tokens:
        text = escape_ass_text(str(token.get("text", "")))
        start = float(token.get("start", token.get("start_time", 0.0)) or 0.0)
        end = float(token.get("end", token.get("end_time", start)) or start)
        dur_cs = max(1, round((end - start) * 100))
        parts.append(rf"{{\k{dur_cs}}}{text}")
    return "".join(parts)


def escape_ass_text(text: str) -> str:
    return text.replace("{", "｛").replace("}", "｝").replace("\n", r"\N")


def build_ass(
    alignment: dict[str, Any],
    *,
    title: str = "ktv-mux lyrics",
    style: dict[str, Any] | None = None,
) -> str:
    style = style or {}
    font_size = int(style.get("font_size") or 48)
    margin_v = int(style.get("margin_v") or 58)
    primary_colour = str(style.get("primary_colour") or "&H00FFFFFF")
    secondary_colour = str(style.get("secondary_colour") or "&H0000D7FF")
    lines = [
        "[Script Info]",
        f"Title: {escape_ass_text(title)}",
        "ScriptType: v4.00+",
        "Collisions: Normal",
        "PlayResX: 1280",
        "PlayResY: 720",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: KTV,Arial Unicode MS,{font_size},{primary_colour},{secondary_colour},&H00000000,&H7F000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for item in alignment.get("lines", []):
        start = seconds_to_ass_time(float(item["start"]))
        end = seconds_to_ass_time(float(item["end"]))
        text = ass_karaoke_text(item.get("tokens") or [])
        if not text:
            text = escape_ass_text(str(item.get("text", "")))
        lines.append(f"Dialogue: 0,{start},{end},KTV,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"
