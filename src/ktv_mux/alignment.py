from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .errors import KtvError, MissingDependencyError
from .lyrics import parse_lyrics_file, split_tokens


def align_lyrics(
    audio_path: Path,
    lyrics_path: Path,
    *,
    duration: float,
    backend: str = "auto",
) -> dict[str, Any]:
    lines = parse_lyrics_file(lyrics_path)
    if not lines:
        raise KtvError(f"lyrics file has no usable lines: {lyrics_path}")

    if backend not in {"auto", "funasr", "simple"}:
        raise KtvError(f"unsupported alignment backend: {backend}")

    if backend in {"auto", "funasr"}:
        try:
            return align_with_funasr(audio_path, lyrics_path, lines)
        except MissingDependencyError:
            if backend == "funasr":
                raise
        except Exception as exc:
            if backend == "funasr":
                raise KtvError(f"FunASR alignment failed: {exc}") from exc

    return generate_even_alignment(lines, duration=duration, backend="simple-even")


def align_with_funasr(audio_path: Path, lyrics_path: Path, lines: list[str]) -> dict[str, Any]:
    try:
        from funasr import AutoModel  # type: ignore
    except Exception as exc:
        raise MissingDependencyError("FunASR is not installed; install ktv-mux[ml]") from exc

    model = AutoModel(model="fa-zh", model_revision="v2.0.4")
    result = model.generate(input=(str(audio_path), str(lyrics_path)), data_type=("sound", "text"))
    parsed = parse_funasr_result(result, lines)
    parsed["backend"] = "funasr-fa-zh"
    parsed["raw_result"] = result
    return parsed


def parse_funasr_result(result: Any, fallback_lines: list[str]) -> dict[str, Any]:
    payload = result[0] if isinstance(result, list) and result else result
    if not isinstance(payload, dict):
        raise KtvError(f"unexpected FunASR result: {type(result).__name__}")

    raw_text = payload.get("text") or "\n".join(fallback_lines)
    token_times = _extract_timestamp_items(payload)
    if not token_times:
        raise KtvError("FunASR result did not contain recognizable timestamps")

    flat_tokens = [token for line in fallback_lines for token in split_tokens(line)]
    if len(token_times) < len(flat_tokens):
        raise KtvError("FunASR returned fewer timestamps than lyric tokens")

    cursor = 0
    aligned_lines: list[dict[str, Any]] = []
    for line in fallback_lines:
        tokens = split_tokens(line)
        count = len(tokens)
        line_times = token_times[cursor : cursor + count]
        cursor += count
        if not line_times:
            continue
        aligned_tokens = []
        for token_text, timing in zip(tokens, line_times, strict=False):
            aligned_tokens.append(
                {
                    "text": token_text,
                    "start": timing["start"],
                    "end": timing["end"],
                }
            )
        aligned_lines.append(
            {
                "start": aligned_tokens[0]["start"],
                "end": aligned_tokens[-1]["end"],
                "text": line,
                "tokens": aligned_tokens,
            }
        )
    return {"backend": "funasr-fa-zh", "text": raw_text, "lines": aligned_lines}


def _extract_timestamp_items(payload: dict[str, Any]) -> list[dict[str, float]]:
    for key in ("timestamp", "timestamps", "time_stamp"):
        value = payload.get(key)
        items = _normalize_timestamp_value(value)
        if items:
            return items
    for key in ("sentence_info", "sentences"):
        value = payload.get(key)
        if isinstance(value, list):
            nested: list[dict[str, float]] = []
            for item in value:
                if isinstance(item, dict):
                    nested.extend(_extract_timestamp_items(item))
            if nested:
                return nested
    return []


def _normalize_timestamp_value(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, float]] = []
    for item in value:
        start: float | None = None
        end: float | None = None
        if isinstance(item, dict):
            start = _seconds(item.get("start") or item.get("start_time") or item.get("begin"))
            end = _seconds(item.get("end") or item.get("end_time") or item.get("finish"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            start = _seconds(item[0])
            end = _seconds(item[1])
        if start is None or end is None:
            continue
        normalized.append({"start": start, "end": max(end, start + 0.01)})
    return normalized


def _seconds(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1000:
        return number / 1000.0
    return number


def generate_even_alignment(
    lines: list[str],
    *,
    duration: float,
    backend: str = "simple-even",
) -> dict[str, Any]:
    duration = max(float(duration or 0.0), float(len(lines)) * 2.0)
    lead = 5.0 if duration > 20 else 0.5
    tail = 2.0 if duration > 20 else 0.5
    usable_start = min(lead, duration * 0.1)
    usable_end = max(usable_start + 1.0, duration - tail)
    total_chars = sum(max(1, len(split_tokens(line))) for line in lines)
    gap = 0.25
    available = max(1.0, usable_end - usable_start - gap * max(0, len(lines) - 1))
    sec_per_char = available / total_chars

    cursor = usable_start
    aligned_lines: list[dict[str, Any]] = []
    for line in lines:
        token_texts = split_tokens(line)
        token_count = max(1, len(token_texts))
        line_start = cursor
        tokens: list[dict[str, Any]] = []
        for token in token_texts:
            token_start = cursor
            cursor += sec_per_char
            tokens.append({"text": token, "start": round(token_start, 3), "end": round(cursor, 3)})
        line_end = max(cursor, line_start + token_count * 0.05)
        aligned_lines.append(
            {
                "start": round(line_start, 3),
                "end": round(line_end, 3),
                "text": line,
                "tokens": tokens,
            }
        )
        cursor = line_end + gap

    return {
        "backend": backend,
        "warning": "Draft timing generated without a forced-alignment model.",
        "lines": aligned_lines,
    }


def shift_alignment(alignment: dict[str, Any], offset_seconds: float) -> dict[str, Any]:
    shifted = copy.deepcopy(alignment)
    offset = float(offset_seconds)
    shifted["manual_offset_seconds"] = round(offset, 3)
    for line in shifted.get("lines", []):
        if not isinstance(line, dict):
            continue
        _shift_timed_item(line, offset)
        for token in line.get("tokens") or []:
            if isinstance(token, dict):
                _shift_timed_item(token, offset)
    return shifted


def _shift_timed_item(item: dict[str, Any], offset: float) -> None:
    start = _shift_time(item.get("start"), offset)
    end = _shift_time(item.get("end"), offset)
    if end <= start:
        end = round(start + 0.01, 3)
    item["start"] = start
    item["end"] = end


def _shift_time(value: Any, offset: float) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 0.0
    return round(max(0.0, seconds + offset), 3)
