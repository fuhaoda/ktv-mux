from __future__ import annotations

from typing import Any

from .jsonio import read_json
from .paths import LibraryPaths, normalize_song_id


def next_actions(library: LibraryPaths, song_id: str) -> list[dict[str, Any]]:
    clean_id = normalize_song_id(song_id)
    report = read_json(library.report_json(clean_id), default={}) or {}
    actions: list[dict[str, Any]] = []
    has_source = bool(library.source_candidates(clean_id))
    if not has_source:
        return [_action("import", "Import source", "No source media is available yet.")]
    if not report.get("probe"):
        actions.append(_action("probe", "Read tracks", "Probe the source before choosing audio tracks."))
    if report.get("probe") and not report.get("track_previews"):
        actions.append(_action("preview-tracks", "Build track previews", "Listen to each source audio track before extraction."))
    if not library.mix_wav(clean_id).exists():
        actions.append(_action("extract", "Extract audio", "Create mix.wav from the chosen source track."))
    if library.mix_wav(clean_id).exists() and not library.instrumental_wav(clean_id).exists():
        actions.append(_action("separate", "Make instrumental", "Run Demucs to create instrumental.wav."))
    if not library.lyrics_txt(clean_id).exists():
        actions.append(_action("lyrics", "Add lyrics", "Save lyrics.txt before making ASS subtitles."))
    if library.lyrics_txt(clean_id).exists() and not library.lyrics_ass(clean_id).exists():
        actions.append(_action("align", "Generate ASS", "Align lyrics and build karaoke ASS."))
    if library.instrumental_wav(clean_id).exists() and not library.audio_replaced_mkv(clean_id).exists():
        actions.append(_action("replace-audio", "Build audio-replaced MKV", "Create a quick MKV with original track plus instrumental."))
    if (
        library.instrumental_wav(clean_id).exists()
        and library.mix_wav(clean_id).exists()
        and library.lyrics_ass(clean_id).exists()
        and not library.final_mkv(clean_id).exists()
    ):
        actions.append(_action("mux", "Build KTV MKV", "Mux video, instrumental, original mix, and ASS lyrics."))
    if not actions:
        actions.append(_action("review", "Review outputs", "Listen, compare takes, and export a package if the result is good."))
    return actions


def _action(stage: str, label: str, reason: str) -> dict[str, Any]:
    return {"stage": stage, "label": label, "reason": reason}
