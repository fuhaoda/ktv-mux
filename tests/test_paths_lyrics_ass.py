from ktv_mux.alignment import generate_even_alignment
from ktv_mux.ass import ass_karaoke_text, build_ass, seconds_to_ass_time
from ktv_mux.lyrics import parse_lyrics_text, split_tokens
from ktv_mux.paths import derive_song_id_from_source, normalize_song_id


def test_normalize_song_id_keeps_chinese_and_removes_separators():
    assert normalize_song_id(" 朋友 周华健 ") == "朋友-周华健"
    assert normalize_song_id("a/b:c") == "a-b-c"


def test_derive_song_id_from_local_filename():
    assert derive_song_id_from_source("assets/朋友-周华健.mkv") == "朋友-周华健"


def test_parse_lyrics_text_ignores_blank_lines():
    assert parse_lyrics_text("第一句\n\n  第二句  \n") == ["第一句", "第二句"]


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
