import json
from pathlib import Path

from ktv_mux.library import build_ytdlp_cmd
from ktv_mux.media import (
    build_demucs_cmd,
    build_extract_mix_cmd,
    build_extract_preview_cmd,
    build_extract_subtitle_cmd,
    build_mux_cmd,
    build_normalize_wav_cmd,
    build_render_audio_wav_cmd,
    build_replace_audio_track_cmd,
    parse_probe_json,
)


def test_parse_probe_json_counts_stream_types():
    payload = {
        "format": {"duration": "3.5", "bit_rate": "120000"},
        "streams": [
            {"codec_type": "video"},
            {"codec_type": "audio"},
            {"codec_type": "audio"},
            {"codec_type": "subtitle"},
        ],
    }
    info = parse_probe_json(json.dumps(payload))
    assert info["duration"] == 3.5
    assert len(info["video_streams"]) == 1
    assert len(info["audio_streams"]) == 2
    assert len(info["subtitle_streams"]) == 1


def test_build_extract_mix_cmd_maps_first_audio():
    cmd = build_extract_mix_cmd(Path("source.mkv"), Path("mix.wav"))
    assert cmd[:3] == ["ffmpeg", "-y", "-hide_banner"]
    assert "-map" in cmd
    assert "0:a:0" in cmd
    assert cmd[-1] == "mix.wav"


def test_build_extract_mix_cmd_can_select_second_audio():
    cmd = build_extract_mix_cmd(Path("source.mkv"), Path("mix.wav"), audio_index=1)
    assert "0:a:1" in cmd


def test_build_extract_preview_cmd_limits_duration():
    cmd = build_extract_preview_cmd(Path("source.mkv"), Path("preview.wav"), audio_index=1, duration=12.5)
    assert "0:a:1" in cmd
    assert "-t" in cmd
    assert "12.500" in cmd


def test_build_extract_preview_cmd_can_start_later():
    cmd = build_extract_preview_cmd(Path("source.mkv"), Path("preview.wav"), start=31.25)
    assert "-ss" in cmd
    assert "31.250" in cmd


def test_build_extract_subtitle_cmd_maps_subtitle_track():
    cmd = build_extract_subtitle_cmd(Path("source.mkv"), Path("lyrics.ass"), subtitle_index=1)
    assert "0:s:1" in cmd
    assert "-c:s" in cmd
    assert cmd[-1] == "lyrics.ass"


def test_build_demucs_cmd_can_select_device():
    cmd = build_demucs_cmd(Path("mix.wav"), Path("demucs"), model="htdemucs_ft", device="cpu")
    assert "htdemucs_ft" in cmd
    assert "-d" in cmd
    assert "cpu" in cmd


def test_build_normalize_wav_cmd_uses_loudnorm():
    cmd = build_normalize_wav_cmd(Path("in.wav"), Path("out.wav"), target_i=-18)
    assert any("loudnorm=I=-18.0" in part for part in cmd)
    assert cmd[-1] == "out.wav"


def test_build_render_audio_wav_cmd_transcodes_external_audio():
    cmd = build_render_audio_wav_cmd(Path("candidate.mp3"), Path("instrumental.wav"))

    assert cmd[:3] == ["ffmpeg", "-y", "-hide_banner"]
    assert "candidate.mp3" in cmd
    assert "-c:a" in cmd
    assert "pcm_s16le" in cmd
    assert "-ar" in cmd
    assert "44100" in cmd
    assert cmd[-1] == "instrumental.wav"


def test_build_render_audio_wav_cmd_can_fit_offset_gain_and_normalize():
    cmd = build_render_audio_wav_cmd(
        Path("candidate.mp3"),
        Path("instrumental.wav"),
        offset=0.5,
        target_duration=30.0,
        gain_db=-2.5,
        normalize=True,
    )

    assert "-af" in cmd
    filters = cmd[cmd.index("-af") + 1]
    assert "adelay=500:all=1" in filters
    assert "apad=whole_dur=30.000" in filters
    assert "atrim=duration=30.000" in filters
    assert "volume=-2.500dB" in filters
    assert "loudnorm=I=-16.0" in filters


def test_build_render_audio_wav_cmd_negative_offset_trims_input():
    cmd = build_render_audio_wav_cmd(Path("candidate.mp3"), Path("instrumental.wav"), offset=-1.25)

    assert "-ss" in cmd
    assert "1.250" in cmd


def test_build_mux_cmd_has_dual_audio_metadata_and_default_instrumental():
    cmd = build_mux_cmd(
        Path("source.mkv"),
        Path("instrumental.wav"),
        Path("mix.wav"),
        Path("lyrics.ass"),
        Path("out.mkv"),
    )
    assert cmd.count("-map") == 4
    assert "title=伴奏" in cmd
    assert "title=原唱" in cmd
    assert "title=歌词" in cmd
    assert "-disposition:s:0" in cmd
    assert cmd[-1] == "out.mkv"


def test_build_mux_cmd_can_keep_original_as_track_one():
    cmd = build_mux_cmd(
        Path("source.mkv"),
        Path("instrumental.wav"),
        Path("mix.wav"),
        Path("lyrics.ass"),
        Path("out.mkv"),
        audio_order="original-first",
    )
    first_audio_map = cmd[cmd.index("0:v:0") + 1 : cmd.index("0:v:0") + 3]
    assert first_audio_map == ["-map", "2:a:0"]
    assert "title=原唱" in cmd
    assert "title=伴奏" in cmd


def test_build_mux_cmd_accepts_track_titles():
    cmd = build_mux_cmd(
        Path("source.mkv"),
        Path("instrumental.wav"),
        Path("mix.wav"),
        Path("lyrics.ass"),
        Path("out.mkv"),
        instrumental_title="Karaoke",
        original_title="Guide",
    )

    assert "title=Karaoke" in cmd
    assert "title=Guide" in cmd


def test_build_ytdlp_cmd_uses_source_template():
    cmd = build_ytdlp_cmd("https://example.invalid/watch?v=1", Path("raw/song"))
    assert cmd[0] == "yt-dlp"
    assert "--write-info-json" in cmd
    assert "raw/song/source.%(ext)s" in cmd


def test_build_replace_audio_track_cmd_preserves_original_as_track_one():
    cmd = build_replace_audio_track_cmd(
        Path("source.mkv"),
        Path("instrumental.wav"),
        Path("out.mkv"),
        keep_audio_index=0,
    )
    assert cmd[cmd.index("0:v:0") + 1 : cmd.index("0:v:0") + 3] == ["-map", "0:a:0"]
    assert "1:a:0" in cmd
    assert "title=原唱" in cmd
    assert "title=伴奏" in cmd
    assert "0:s?" in cmd


def test_build_replace_audio_track_cmd_can_skip_subtitles_and_rename_tracks():
    cmd = build_replace_audio_track_cmd(
        Path("source.mkv"),
        Path("instrumental.wav"),
        Path("out.mkv"),
        keep_audio_index=0,
        copy_subtitles=False,
        instrumental_title="Karaoke",
        original_title="Guide",
    )

    assert "0:s?" not in cmd
    assert "title=Karaoke" in cmd
    assert "title=Guide" in cmd
