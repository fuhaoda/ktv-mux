from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .paths import normalize_song_id

_BASE_TEMPLATE = Path(__file__).with_name("templates") / "base.html"

def page(title: str, body: str, *, auto_refresh: bool = False, refresh_seconds: int = 3) -> str:
    refresh = f'<meta http-equiv="refresh" content="{int(refresh_seconds)}">' if auto_refresh else ""
    template = _BASE_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("{{ refresh }}", refresh)
        .replace("{{ title }}", escape(title))
        .replace("{{ body }}", body)
    )

def render_select_options(values: list[str], selected_value: str) -> str:
    return "".join(
        f"<option value='{escape(value)}'{' selected' if value == selected_value else ''}>{escape(value)}</option>"
        for value in values
    )

def render_audio_options(report: dict[str, Any], selected_index: int) -> str:
    audio_streams = []
    for stream in ((report or {}).get("probe") or {}).get("streams") or []:
        if stream.get("codec_type") == "audio":
            audio_streams.append(stream)
    if not audio_streams:
        audio_streams = [{"index": 0}, {"index": 1}]

    options = []
    for audio_index, stream in enumerate(audio_streams):
        selected = " selected" if audio_index == selected_index else ""
        details = audio_details(stream)
        label = f"Track {audio_index + 1}"
        if details:
            label = f"{label} - {details}"
        options.append(f"<option value='{audio_index}'{selected}>{escape(label)}</option>")
    return "".join(options)

def audio_details(stream: dict[str, Any]) -> str:
    codec = stream.get("codec_name") or "audio"
    channels = stream.get("channels")
    sample_rate = stream.get("sample_rate")
    language = (stream.get("tags") or {}).get("language")
    title = (stream.get("tags") or {}).get("title")
    default = "default" if (stream.get("disposition") or {}).get("default") else ""
    values = [codec, sample_rate, f"{channels}ch" if channels else "", language, title, default]
    return " ".join(str(item) for item in values if item)

def render_flags(song: dict[str, Any]) -> str:
    labels = [
        ("has_source", "source"),
        ("has_lyrics", "lyrics"),
        ("has_mix", "mix"),
        ("has_instrumental", "instrumental"),
        ("has_ass", "ass"),
        ("has_audio_replaced_mkv", "audio-mkv"),
        ("has_mkv", "ktv-mkv"),
    ]
    return " ".join(f"<span class='flag'>{escape(label)}</span>" for key, label in labels if song.get(key))

def render_delete_confirm(song_id: str) -> str:
    return f"""
<section class="panel danger-zone stack">
  <h1>Confirm Delete</h1>
  <div class="subtle">Type the exact song ID before deleting.</div>
  <form method="post" action="{song_url(song_id)}/delete" class="stack">
    <label>Song ID</label>
    <input name="confirm" placeholder="{escape(song_id)}">
    <div class="row">
      <button class="danger" type="submit">Delete Song</button>
      <a class="button secondary" href="{song_url(song_id)}">Cancel</a>
    </div>
  </form>
</section>
"""

def render_error(message: str, trace: str) -> str:
    return f"""
<section class="hero"><div><h1>Something Needs Attention</h1><div class="subtle">The request did not complete.</div></div></section>
<section class="panel stack">
  <div class="badge bad">{escape(trim(message, 300))}</div>
  <pre>{escape(trace)}</pre>
  <div><a class="button secondary" href="/">Back to songs</a></div>
</section>
"""

def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        return {}
    clone = dict(report)
    probe = clone.get("probe")
    if isinstance(probe, dict):
        clone["probe"] = {
            "duration": probe.get("duration"),
            "video_streams": probe.get("video_streams"),
            "audio_streams": probe.get("audio_streams"),
            "subtitle_streams": probe.get("subtitle_streams"),
        }
    if clone.get("failure"):
        clone["failure"] = trim(str(clone["failure"]), 1200)
    return clone

def song_url(song_id: str) -> str:
    return f"/songs/{quote(normalize_song_id(song_id), safe='')}"

def trim(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "..."

def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return escape(str(value))

def fmt_attr(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return escape(str(value))

def fmt_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return escape(str(value))

def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
