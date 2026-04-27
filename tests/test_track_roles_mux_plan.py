import ktv_mux.pipeline as pipeline_module
from ktv_mux.jsonio import write_json
from ktv_mux.mux_plan import ktv_mux_plan, replace_audio_plan
from ktv_mux.paths import LibraryPaths
from ktv_mux.pipeline import Pipeline
from ktv_mux.track_roles import track_role_report
from ktv_mux.versions import take_kind


def test_track_role_infers_default_and_manual_override(monkeypatch, tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"source")
    write_json(
        library.report_json("song"),
        {
            "probe": {
                "streams": [
                    {"codec_type": "audio", "codec_name": "aac", "disposition": {"default": 1}, "tags": {}},
                    {"codec_type": "audio", "codec_name": "aac", "disposition": {}, "tags": {"title": "伴奏"}},
                ]
            }
        },
    )

    report = library.report_json("song").read_text(encoding="utf-8")
    assert "track_roles" not in report
    role = track_role_report({"track_roles": {}, "probe": {}}, 0, {"disposition": {"default": 1}, "tags": {}})
    assert role["role"] == "guide-vocal"

    monkeypatch.setattr(pipeline_module, "_validate_audio_index", lambda source, audio_index: None)

    result = Pipeline(library).set_track_role("song", audio_index=1, role="instrumental", note="good backing")

    assert result["role"] == "instrumental"
    assert "good backing" in library.report_json("song").read_text(encoding="utf-8")


def test_mux_plans_show_track_order_and_readiness():
    summary = {"has_source": True, "has_mix": True, "has_instrumental": True, "has_ass": True}
    report = {"probe": {"streams": [{"codec_type": "audio", "disposition": {"default": 1}, "tags": {}}]}}

    ktv = ktv_mux_plan(summary, report, audio_order="original-first")
    replaced = replace_audio_plan(summary, report, keep_audio_index=0)

    assert ktv["ready"] is True
    assert ktv["audio"][0]["source"] == "mix.wav"
    assert ktv["audio"][1]["source"] == "instrumental.wav"
    assert replaced["ready"] is True
    assert replaced["audio"][0]["source"] == "source Track 1"
    assert replaced["audio"][1]["role"] == "instrumental"


def test_sample_take_kind_is_distinct():
    assert take_kind("instrumental.sample.20260426T010000Z.wav") == "instrumental-sample"


def test_batch_recipe_dry_run_lists_song_and_stages(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")

    plan = Pipeline(library).batch_recipe("instrumental-review", dry_run=True)

    assert plan["dry_run"] is True
    assert plan["recipe"] == "instrumental-review"
    assert plan["songs"] == [{"song_id": "song", "stages": ["probe", "preview-tracks", "separate-sample"]}]
