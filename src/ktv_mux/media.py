from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .commands import require_command, run_command, run_command_logged
from .errors import KtvError


def build_ffprobe_cmd(path: Path) -> list[str]:
    return [
        "ffprobe",
        "-hide_banner",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]


def probe_media(path: Path) -> dict[str, Any]:
    require_command("ffprobe")
    result = run_command(build_ffprobe_cmd(path))
    return parse_probe_json(result.stdout)


def parse_probe_json(text: str) -> dict[str, Any]:
    data = json.loads(text)
    streams = data.get("streams") or []
    format_info = data.get("format") or {}
    return {
        "format": format_info,
        "duration": _float_or_none(format_info.get("duration")),
        "bit_rate": _int_or_none(format_info.get("bit_rate")),
        "streams": streams,
        "video_streams": [s for s in streams if s.get("codec_type") == "video"],
        "audio_streams": [s for s in streams if s.get("codec_type") == "audio"],
        "subtitle_streams": [s for s in streams if s.get("codec_type") == "subtitle"],
    }


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_extract_mix_cmd(source: Path, output_wav: Path, *, audio_index: int = 0) -> list[str]:
    if audio_index < 0:
        raise KtvError("audio_index must be 0 or greater")
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(source),
        "-map",
        f"0:a:{audio_index}",
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        str(output_wav),
    ]


def build_extract_preview_cmd(
    source: Path,
    output_wav: Path,
    *,
    audio_index: int = 0,
    duration: float = 20.0,
    start: float = 0.0,
) -> list[str]:
    if audio_index < 0:
        raise KtvError("audio_index must be 0 or greater")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(source),
        "-map",
        f"0:a:{audio_index}",
        "-t",
        f"{duration:.3f}",
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        str(output_wav),
    ]
    if start > 0:
        cmd[5:5] = ["-ss", f"{start:.3f}"]
    return cmd


def extract_mix(
    source: Path,
    output_wav: Path,
    *,
    audio_index: int = 0,
    cancel_file: Path | None = None,
) -> Path:
    require_command("ffmpeg")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    run_command(build_extract_mix_cmd(source, output_wav, audio_index=audio_index), cancel_file=cancel_file)
    return output_wav


def extract_preview(
    source: Path,
    output_wav: Path,
    *,
    audio_index: int = 0,
    duration: float = 20.0,
    start: float = 0.0,
    cancel_file: Path | None = None,
) -> Path:
    require_command("ffmpeg")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        build_extract_preview_cmd(source, output_wav, audio_index=audio_index, duration=duration, start=start),
        cancel_file=cancel_file,
    )
    return output_wav


def detect_torch_device() -> str | None:
    try:
        import torch  # type: ignore
    except Exception:
        return None
    try:
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        return None
    return None


def build_demucs_cmd(
    mix_wav: Path,
    demucs_out_dir: Path,
    *,
    model: str = "htdemucs",
    device: str | None = None,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        model,
        "--two-stems",
        "vocals",
        "-o",
        str(demucs_out_dir),
    ]
    if device:
        cmd.extend(["-d", device])
    cmd.append(str(mix_wav))
    return cmd


def run_demucs_two_stems(
    mix_wav: Path,
    work_dir: Path,
    output_instrumental: Path,
    output_vocals: Path,
    *,
    model: str = "htdemucs",
    device: str | None = None,
    log_path: Path | None = None,
    cancel_file: Path | None = None,
) -> dict[str, Any]:
    demucs_root = work_dir / "demucs"
    demucs_root.mkdir(parents=True, exist_ok=True)
    detected_device = detect_torch_device()
    requested_device = None if device in {None, "", "auto"} else str(device)
    attempted: list[str | None] = []

    for candidate in _device_attempts(requested_device or detected_device):
        attempted.append(candidate)
        try:
            cmd = build_demucs_cmd(mix_wav, demucs_root, model=model, device=candidate)
            if log_path:
                run_command_logged(cmd, log_path=log_path, cancel_file=cancel_file)
            else:
                run_command(cmd, cancel_file=cancel_file)
            break
        except KtvError:
            if candidate == "cpu":
                raise
            continue
    else:
        raise KtvError("demucs did not run")

    track_dir = demucs_root / model / mix_wav.stem
    vocals = track_dir / "vocals.wav"
    no_vocals = track_dir / "no_vocals.wav"
    if not vocals.exists() or not no_vocals.exists():
        raise KtvError(f"Demucs outputs not found under {track_dir}")

    output_instrumental.parent.mkdir(parents=True, exist_ok=True)
    output_vocals.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(no_vocals, output_instrumental)
    shutil.copy2(vocals, output_vocals)
    return {
        "model": model,
        "requested_device": requested_device or "auto",
        "detected_device": detected_device,
        "attempted_devices": attempted,
        "instrumental": str(output_instrumental),
        "vocals": str(output_vocals),
    }


def _device_attempts(device: str | None) -> Iterable[str | None]:
    if device:
        yield device
        if device != "cpu":
            yield "cpu"
    else:
        yield None


def build_mux_cmd(
    source_video: Path,
    instrumental_wav: Path,
    original_mix_wav: Path,
    lyrics_ass: Path,
    output_mkv: Path,
    *,
    duration_limit: float | None = None,
    audio_order: str = "instrumental-first",
) -> list[str]:
    if audio_order not in {"instrumental-first", "original-first"}:
        raise KtvError(f"unsupported audio_order: {audio_order}")
    if audio_order == "instrumental-first":
        audio_inputs = [
            ("1:a:0", "伴奏", "default"),
            ("2:a:0", "原唱", "0"),
        ]
    else:
        audio_inputs = [
            ("2:a:0", "原唱", "0"),
            ("1:a:0", "伴奏", "default"),
        ]

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(source_video),
        "-i",
        str(instrumental_wav),
        "-i",
        str(original_mix_wav),
        "-i",
        str(lyrics_ass),
        "-map",
        "0:v:0",
    ]
    for stream_map, _title, _disposition in audio_inputs:
        cmd.extend(["-map", stream_map])
    cmd.extend(
        [
        "-map",
        "3:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-c:s",
        "ass",
        ]
    )
    for index, (_stream_map, title, disposition) in enumerate(audio_inputs):
        cmd.extend(
            [
                f"-metadata:s:a:{index}",
                f"title={title}",
                f"-metadata:s:a:{index}",
                "language=zho",
                f"-disposition:a:{index}",
                disposition,
            ]
        )
    cmd.extend(
        [
        "-metadata:s:s:0",
        "title=歌词",
        "-metadata:s:s:0",
        "language=zho",
        "-disposition:s:0",
        "default",
        ]
    )
    if duration_limit is not None:
        cmd.extend(["-t", f"{duration_limit:.3f}"])
    cmd.append(str(output_mkv))
    return cmd


def mux_ktv(
    source_video: Path,
    instrumental_wav: Path,
    original_mix_wav: Path,
    lyrics_ass: Path,
    output_mkv: Path,
    *,
    duration_limit: float | None = None,
    audio_order: str = "instrumental-first",
    cancel_file: Path | None = None,
) -> Path:
    require_command("ffmpeg")
    output_mkv.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        build_mux_cmd(
            source_video,
            instrumental_wav,
            original_mix_wav,
            lyrics_ass,
            output_mkv,
            duration_limit=duration_limit,
            audio_order=audio_order,
        ),
        cancel_file=cancel_file,
    )
    return output_mkv


def build_replace_audio_track_cmd(
    source_video: Path,
    instrumental_wav: Path,
    output_mkv: Path,
    *,
    keep_audio_index: int = 0,
    copy_subtitles: bool = True,
    duration_limit: float | None = None,
) -> list[str]:
    if keep_audio_index < 0:
        raise KtvError("keep_audio_index must be 0 or greater")

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(source_video),
        "-i",
        str(instrumental_wav),
        "-map",
        "0:v:0",
        "-map",
        f"0:a:{keep_audio_index}",
        "-map",
        "1:a:0",
    ]
    if copy_subtitles:
        cmd.extend(["-map", "0:s?"])
    cmd.extend(
        [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-c:s",
            "copy",
            "-metadata:s:a:0",
            "title=原唱",
            "-metadata:s:a:0",
            "language=zho",
            "-metadata:s:a:1",
            "title=伴奏",
            "-metadata:s:a:1",
            "language=zho",
            "-disposition:a:0",
            "default",
            "-disposition:a:1",
            "0",
        ]
    )
    if duration_limit is not None:
        cmd.extend(["-t", f"{duration_limit:.3f}"])
    cmd.append(str(output_mkv))
    return cmd


def replace_audio_track(
    source_video: Path,
    instrumental_wav: Path,
    output_mkv: Path,
    *,
    keep_audio_index: int = 0,
    copy_subtitles: bool = True,
    duration_limit: float | None = None,
    cancel_file: Path | None = None,
) -> Path:
    require_command("ffmpeg")
    output_mkv.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        build_replace_audio_track_cmd(
            source_video,
            instrumental_wav,
            output_mkv,
            keep_audio_index=keep_audio_index,
            copy_subtitles=copy_subtitles,
            duration_limit=duration_limit,
        ),
        cancel_file=cancel_file,
    )
    return output_mkv


def build_normalize_wav_cmd(
    input_wav: Path,
    output_wav: Path,
    *,
    target_i: float = -16.0,
    target_tp: float = -1.5,
    target_lra: float = 11.0,
) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(input_wav),
        "-af",
        f"loudnorm=I={target_i:.1f}:TP={target_tp:.1f}:LRA={target_lra:.1f}",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-c:a",
        "pcm_s16le",
        str(output_wav),
    ]


def normalize_wav(
    input_wav: Path,
    output_wav: Path,
    *,
    target_i: float = -16.0,
    cancel_file: Path | None = None,
) -> Path:
    require_command("ffmpeg")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    run_command(build_normalize_wav_cmd(input_wav, output_wav, target_i=target_i), cancel_file=cancel_file)
    return output_wav
