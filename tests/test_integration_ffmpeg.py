from pathlib import Path

import pytest

from ktv_mux.alignment import generate_even_alignment
from ktv_mux.ass import build_ass
from ktv_mux.commands import require_command, run_command
from ktv_mux.media import extract_mix, mux_ktv, probe_media, replace_audio_track

ASSET = Path("assets/朋友-周华健.mkv")


pytestmark = pytest.mark.integration


def test_probe_sample_asset_has_expected_streams():
    if not ASSET.exists():
        pytest.skip("sample asset not present")
    require_command("ffprobe")
    info = probe_media(ASSET)
    assert len(info["video_streams"]) == 1
    assert len(info["audio_streams"]) == 2
    assert len(info["subtitle_streams"]) == 1


def test_mux_short_sample_with_generated_ass(tmp_path):
    if not ASSET.exists():
        pytest.skip("sample asset not present")
    require_command("ffmpeg")
    require_command("ffprobe")

    mix = tmp_path / "mix.wav"
    instrumental = tmp_path / "instrumental.wav"
    ass = tmp_path / "lyrics.ass"
    out = tmp_path / "out.mkv"

    extract_mix(ASSET, mix)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-t",
            "3",
            "-i",
            str(mix),
            "-c:a",
            "pcm_s16le",
            str(instrumental),
        ]
    )
    alignment = generate_even_alignment(["朋友一生一起走", "那些日子不再有"], duration=3)
    ass.write_text(build_ass(alignment), encoding="utf-8")

    mux_ktv(ASSET, instrumental, mix, ass, out, duration_limit=3)
    info = probe_media(out)
    assert len(info["video_streams"]) == 1
    assert len(info["audio_streams"]) == 2
    assert len(info["subtitle_streams"]) == 1


def test_replace_audio_track_short_sample(tmp_path):
    if not ASSET.exists():
        pytest.skip("sample asset not present")
    require_command("ffmpeg")
    require_command("ffprobe")

    mix = tmp_path / "mix.wav"
    instrumental = tmp_path / "instrumental.wav"
    out = tmp_path / "audio-replaced.mkv"

    extract_mix(ASSET, mix, audio_index=0)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-t",
            "3",
            "-i",
            str(mix),
            "-af",
            "volume=0.5",
            "-c:a",
            "pcm_s16le",
            str(instrumental),
        ]
    )
    replace_audio_track(ASSET, instrumental, out, duration_limit=3)
    info = probe_media(out)
    assert len(info["video_streams"]) == 1
    assert len(info["audio_streams"]) == 2
