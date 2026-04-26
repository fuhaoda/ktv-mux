import struct
import wave

from ktv_mux.quality import analyze_wav, mkv_audit_report, separation_quality_report


def write_wav(path, amplitude):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        frames = b"".join(struct.pack("<h", amplitude if index % 2 == 0 else -amplitude) for index in range(800))
        wav.writeframes(frames)


def write_wav_with_frames(path, amplitude, frames):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        data = b"".join(struct.pack("<h", amplitude if index % 2 == 0 else -amplitude) for index in range(frames))
        wav.writeframes(data)


def test_analyze_wav_reports_duration_and_levels(tmp_path):
    path = tmp_path / "tone.wav"
    write_wav(path, 1000)

    info = analyze_wav(path)

    assert info["exists"] is True
    assert info["duration"] == 0.1
    assert info["sample_rate"] == 8000
    assert info["rms_dbfs"] is not None
    assert info["clipped_ratio"] == 0
    assert info["silence_ratio"] == 0


def test_analyze_wav_detects_clipping_and_silence(tmp_path):
    clipped = tmp_path / "clipped.wav"
    silent = tmp_path / "silent.wav"
    write_wav(clipped, 32767)
    write_wav(silent, 0)

    assert analyze_wav(clipped)["clipped_ratio"] > 0
    assert analyze_wav(silent)["silence_ratio"] == 1.0


def test_separation_quality_report_compares_stems(tmp_path):
    mix = tmp_path / "mix.wav"
    instrumental = tmp_path / "instrumental.wav"
    vocals = tmp_path / "vocals.wav"
    write_wav(mix, 1000)
    write_wav(instrumental, 500)
    write_wav(vocals, 250)

    report = separation_quality_report(mix_wav=mix, instrumental_wav=instrumental, vocals_wav=vocals)

    assert report["instrumental"]["exists"] is True
    assert report["instrumental_rms_delta_db"] < 0
    assert report["vocals_rms_delta_db"] < report["instrumental_rms_delta_db"]
    assert report["recommendations"]


def test_quality_report_warns_on_duration_mismatch(tmp_path):
    mix = tmp_path / "mix.wav"
    instrumental = tmp_path / "instrumental.wav"
    vocals = tmp_path / "vocals.wav"
    write_wav_with_frames(mix, 1000, 8000)
    write_wav_with_frames(instrumental, 1000, 800)
    write_wav_with_frames(vocals, 1000, 8000)

    report = separation_quality_report(mix_wav=mix, instrumental_wav=instrumental, vocals_wav=vocals)

    assert report["duration_delta_seconds"] > 0.5
    assert any("duration" in item.lower() for item in report["recommendations"])


def test_mkv_audit_report_checks_stream_counts_and_defaults():
    report = mkv_audit_report(
        {
            "duration": 3.0,
            "video_streams": [{"codec_type": "video"}],
            "audio_streams": [{"tags": {"title": "伴奏"}, "disposition": {"default": 1}}],
            "subtitle_streams": [],
        }
    )

    assert report["ok"] is False
    assert report["audio_streams"] == 1
    assert report["warnings"]
