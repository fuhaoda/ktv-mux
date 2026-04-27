from ktv_mux.jsonio import write_json
from ktv_mux.paths import LibraryPaths
from ktv_mux.preflight import song_preflight


def test_preflight_reports_modular_readiness(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"source")
    library.mix_wav("song").write_bytes(b"mix")
    library.instrumental_wav("song").write_bytes(b"instrumental")
    library.lyrics_ass("song").write_text("ass", encoding="utf-8")
    write_json(
        library.report_json("song"),
        {"external_instrumental_fit": {"warnings": ["Duration differs from mix by 1.000s."]}},
    )

    result = song_preflight(library, "song")

    assert result["ok_for_instrumental_review"] is True
    assert result["ok_for_replace_audio"] is True
    assert result["ok_for_final_mkv"] is True
    assert "Duration differs" in result["warnings"][0]


def test_preflight_distinguishes_sample_review_from_full_instrumental(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"source")
    library.instrumental_sample_wav("song").write_bytes(b"sample")

    result = song_preflight(library, "song")

    assert result["ok_for_sample_review"] is True
    assert result["ok_for_instrumental_review"] is False
    assert result["ok_for_replace_audio"] is False


def test_preflight_filters_non_blocking_positive_recommendations(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"source")
    write_json(
        library.report_json("song"),
        {
            "quality": {
                "recommendations_zh": [
                    "没有发现明显电平问题；建议用播放器试听最终效果。",
                    "残留人声风险较高；建议先试听副歌片段，再决定是否替换第 2 轨。",
                ]
            }
        },
    )

    result = song_preflight(library, "song")

    assert result["warnings"] == ["残留人声风险较高；建议先试听副歌片段，再决定是否替换第 2 轨。"]
