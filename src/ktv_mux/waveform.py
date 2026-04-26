from __future__ import annotations

import wave
from html import escape
from pathlib import Path


def wav_waveform_svg(path: Path, *, width: int = 900, height: int = 120) -> str:
    if not path.exists():
        return _empty_svg(width, height, "No audio waveform yet.")
    try:
        with wave.open(str(path), "rb") as wav:
            sample_width = wav.getsampwidth()
            channels = max(1, wav.getnchannels())
            frames = wav.getnframes()
            raw = wav.readframes(frames)
    except Exception as exc:
        return _empty_svg(width, height, f"Could not read waveform: {exc}")

    sample_count = len(raw) // max(1, sample_width)
    if sample_count == 0:
        return _empty_svg(width, height, "Empty audio file.")
    full_scale = float((1 << (8 * sample_width - 1)) - 1)
    bucket_count = max(80, min(width, 1200))
    samples_per_bucket = max(channels, sample_count // bucket_count)
    peaks: list[float] = []
    for bucket_start in range(0, sample_count, samples_per_bucket):
        bucket_end = min(sample_count, bucket_start + samples_per_bucket)
        peak = 0
        for index in range(bucket_start, bucket_end):
            offset = index * sample_width
            peak = max(peak, abs(_pcm_sample(raw[offset : offset + sample_width], sample_width)))
        peaks.append(min(1.0, peak / full_scale if full_scale else 0.0))

    mid = height / 2
    lines = []
    for index, peak in enumerate(peaks):
        x = round(index * (width / max(1, len(peaks) - 1)), 2)
        half = max(1.0, peak * (height * 0.43))
        lines.append(
            f"<line x1='{x}' y1='{round(mid - half, 2)}' x2='{x}' y2='{round(mid + half, 2)}' "
            "stroke='#0b63ce' stroke-width='1' />"
        )
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
        "role='img' aria-label='audio waveform'>"
        "<rect width='100%' height='100%' rx='6' fill='#f8fbff'/>"
        f"<line x1='0' y1='{mid}' x2='{width}' y2='{mid}' stroke='#ccd7e5' stroke-width='1'/>"
        f"{''.join(lines)}</svg>"
    )


def _empty_svg(width: int, height: int, message: str) -> str:
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
        "role='img'>"
        "<rect width='100%' height='100%' rx='6' fill='#f8fbff'/>"
        f"<text x='16' y='{height / 2}' fill='#637083' font-family='system-ui' font-size='13'>"
        f"{escape(message)}</text></svg>"
    )


def _pcm_sample(chunk: bytes, sample_width: int) -> int:
    if sample_width == 1:
        return chunk[0] - 128
    if sample_width == 3:
        sign_byte = b"\xff" if chunk[2] & 0x80 else b"\x00"
        return int.from_bytes(chunk + sign_byte, "little", signed=True)
    return int.from_bytes(chunk, "little", signed=True)
