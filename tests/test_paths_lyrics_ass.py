from ktv_mux.alignment import (
    align_lyrics,
    generate_even_alignment,
    shift_alignment,
    shift_alignment_lines,
    stretch_alignment_lines,
    update_alignment_lines,
)
from ktv_mux.ass import ass_karaoke_text, build_ass, seconds_to_ass_time
from ktv_mux.lyrics import (
    ass_text_to_alignment,
    extract_lrc_entries,
    lrc_text_to_alignment,
    normalize_lyrics_text,
    parse_lrc_text,
    parse_lyrics_text,
    split_tokens,
    srt_text_to_alignment,
)
from ktv_mux.paths import LibraryPaths, derive_song_id_from_source, normalize_song_id


def test_normalize_song_id_keeps_chinese_and_removes_separators():
    assert normalize_song_id(" 朋友 周华健 ") == "朋友-周华健"
    assert normalize_song_id("a/b:c") == "a-b-c"


def test_derive_song_id_from_local_filename():
    assert derive_song_id_from_source("assets/朋友-周华健.mkv") == "朋友-周华健"


def test_library_paths_include_previews_and_takes(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    assert library.track_preview_wav("song", 1).name == "track-2.wav"
    assert library.instrumental_sample_wav("song").name == "instrumental.sample.wav"
    assert library.lyrics_versions_dir("song").name == "lyrics-versions"
    assert library.takes_dir("song").exists()


def test_parse_lyrics_text_ignores_blank_lines():
    assert parse_lyrics_text("第一句\n\n  第二句  \n") == ["第一句", "第二句"]


def test_lyrics_cleanup_handles_lrc_timestamps_and_chords():
    text = "[00:01.00][C]  第一  句　歌词\n[00:02.00]第二句"
    assert parse_lrc_text(text) == ["第一 句 歌词", "第二句"]
    assert normalize_lyrics_text(text) == "第一 句 歌词\n第二句"


def test_lrc_timestamps_become_initial_alignment():
    text = "[00:01.00]朋友一生一起走\n[00:04.50]那些日子不再有"

    entries = extract_lrc_entries(text)
    alignment = lrc_text_to_alignment(text)

    assert entries[0]["start"] == 1.0
    assert alignment["backend"] == "lrc"
    assert alignment["lines"][0]["start"] == 1.0
    assert alignment["lines"][0]["end"] == 4.5
    assert alignment["lines"][0]["tokens"][0]["text"] == "朋"


def test_srt_text_to_alignment_extracts_timed_lines():
    alignment = srt_text_to_alignment(
        "1\n00:00:01,000 --> 00:00:03,500\n朋友一生一起走\n\n2\n00:00:04.000 --> 00:00:05.000\n第二句\n"
    )

    assert alignment["backend"] == "srt"
    assert alignment["lines"][0]["start"] == 1.0
    assert alignment["lines"][0]["end"] == 3.5
    assert alignment["lines"][0]["text"] == "朋友一生一起走"


def test_ass_text_to_alignment_extracts_dialogues():
    alignment = ass_text_to_alignment(
        "[Events]\n"
        "Format: Layer, Start, End, Style, Text\n"
        r"Dialogue: 0,0:00:01.00,0:00:03.00,Default,{\k25}朋友\N一起走"
        "\n"
    )

    assert alignment["backend"] == "ass"
    assert alignment["lines"][0]["start"] == 1.0
    assert alignment["lines"][0]["text"] == "朋友 一起走"


def test_split_tokens_uses_chars_for_chinese_and_words_for_spaced_text():
    assert split_tokens("朋友一生一起走") == list("朋友一生一起走")
    assert split_tokens("hello world") == ["hello", "world"]


def test_ass_time_and_karaoke_text():
    assert seconds_to_ass_time(65.432) == "0:01:05.43"
    text = ass_karaoke_text(
        [
            {"text": "朋", "start": 1.0, "end": 1.25},
            {"text": "友", "start": 1.25, "end": 1.6},
        ]
    )
    assert text == r"{\k25}朋{\k35}友"


def test_build_ass_contains_karaoke_dialogue():
    alignment = generate_even_alignment(["朋友一生一起走"], duration=12)
    ass = build_ass(alignment, title="朋友")
    assert "[Script Info]" in ass
    assert "Dialogue:" in ass
    assert r"{\k" in ass


def test_build_ass_accepts_style_overrides():
    alignment = generate_even_alignment(["朋友"], duration=2)
    ass = build_ass(
        alignment,
        title="朋友",
        style={"font_size": 56, "margin_v": 72, "primary_colour": "&H00F0F0F0", "secondary_colour": "&H000000FF"},
    )

    assert "Style: KTV,Arial Unicode MS,56,&H00F0F0F0,&H000000FF" in ass
    assert ",72,1" in ass


def test_shift_alignment_moves_lines_and_tokens():
    alignment = generate_even_alignment(["朋友"], duration=4)
    shifted = shift_alignment(alignment, 0.5)

    assert shifted["manual_offset_seconds"] == 0.5
    assert shifted["lines"][0]["start"] == alignment["lines"][0]["start"] + 0.5
    assert shifted["lines"][0]["tokens"][0]["start"] == alignment["lines"][0]["tokens"][0]["start"] + 0.5


def test_shift_alignment_lines_only_moves_requested_range():
    alignment = generate_even_alignment(["第一句", "第二句"], duration=8)
    shifted = shift_alignment_lines(alignment, start_index=1, end_index=1, offset_seconds=0.5)

    assert shifted["lines"][0]["start"] == alignment["lines"][0]["start"]
    assert shifted["lines"][1]["start"] == alignment["lines"][1]["start"] + 0.5


def test_stretch_alignment_lines_retakes_range_window():
    alignment = generate_even_alignment(["第一句", "第二句"], duration=8)
    stretched = stretch_alignment_lines(alignment, start_index=0, end_index=1, target_start=10, target_end=20)

    assert stretched["lines"][0]["start"] == 10
    assert stretched["lines"][1]["end"] == 20
    assert stretched["manual_stretch_window"] == [10, 20]


def test_align_lyrics_can_use_original_lrc(tmp_path):
    lyrics = tmp_path / "lyrics.txt"
    lrc = tmp_path / "lyrics.original.lrc"
    audio = tmp_path / "audio.wav"
    lyrics.write_text("第一句\n第二句\n", encoding="utf-8")
    lrc.write_text("[00:01.00]第一句\n[00:03.00]第二句\n", encoding="utf-8")
    audio.write_bytes(b"")

    alignment = align_lyrics(audio, lyrics, duration=5, backend="lrc", lrc_path=lrc)

    assert alignment["backend"] == "lrc"
    assert alignment["lines"][0]["start"] == 1.0


def test_update_alignment_lines_retimes_tokens():
    alignment = generate_even_alignment(["朋友"], duration=4)
    edited = update_alignment_lines(alignment, [{"index": 0, "start": 1.0, "end": 2.0, "text": "新朋友"}])

    assert edited["manual_edits"] is True
    assert edited["lines"][0]["start"] == 1.0
    assert edited["lines"][0]["end"] == 2.0
    assert edited["lines"][0]["text"] == "新朋友"
    assert edited["lines"][0]["tokens"][0]["start"] == 1.0
    assert edited["lines"][0]["tokens"][-1]["end"] == 2.0
