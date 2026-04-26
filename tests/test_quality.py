import struct
import wave

from ktv_mux.quality import analyze_wav, separation_quality_report


def write_wav(path, amplitude):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        frames = b"".join(struct.pack("<h", amplitude if index % 2 == 0 else -amplitude) for index in range(800))
        wav.writeframes(frames)


def test_analyze_wav_reports_duration_and_levels(tmp_path):
    path = tmp_path / "tone.wav"
    write_wav(path, 1000)

    info = analyze_wav(path)

    assert info["exists"] is True
    assert info["duration"] == 0.1
    assert info["sample_rate"] == 8000
    assert info["rms_dbfs"] is not None


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
