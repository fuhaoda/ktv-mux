from ktv_mux.jobs import Job, LocalJobRunner, run_pipeline_stage
from ktv_mux.jsonio import read_json
from ktv_mux.paths import LibraryPaths


class FakePipeline:
    def __init__(self):
        self.calls = []

    def extract(self, song_id, *, audio_index=0):
        self.calls.append(("extract", song_id, audio_index))

    def shift_subtitles(self, song_id, *, seconds=0.0):
        self.calls.append(("shift-subtitles", song_id, seconds))


def test_job_runner_submit_persists_queue_state(tmp_path):
    library = LibraryPaths(tmp_path / "library")
    runner = LocalJobRunner(library, FakePipeline())

    job = runner.submit("朋友 周华健", "extract", {"audio_index": 1})

    saved = read_json(library.job_json(job.job_id))
    status = read_json(library.status_json("朋友-周华健"))
    assert saved["song_id"] == "朋友-周华健"
    assert saved["state"] == "queued"
    assert status["state"] == "queued"
    assert runner.list_jobs()[0].job_id == job.job_id


def test_run_pipeline_stage_passes_stage_parameters():
    pipeline = FakePipeline()

    run_pipeline_stage(pipeline, Job(job_id="1", song_id="song", stage="extract", params={"audio_index": 2}))
    run_pipeline_stage(
        pipeline,
        Job(job_id="2", song_id="song", stage="shift-subtitles", params={"seconds": "-0.25"}),
    )

    assert pipeline.calls == [("extract", "song", 2), ("shift-subtitles", "song", -0.25)]
