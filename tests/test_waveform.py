import struct
import wave

from ktv_mux.waveform import wav_waveform_svg


def test_wav_waveform_svg_renders_audio_peaks(tmp_path):
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"".join(struct.pack("<h", 1000) for _ in range(800)))

    svg = wav_waveform_svg(path)

    assert svg.startswith("<svg")
    assert "<line" in svg
