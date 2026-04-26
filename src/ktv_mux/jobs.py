from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from .jsonio import read_json, write_json
from .models import append_stage_status, utc_now
from .paths import LibraryPaths, normalize_song_id
from .pipeline import Pipeline
from .progress import estimate_stage_progress


@dataclass
class Job:
    job_id: str
    song_id: str
    stage: str
    params: dict[str, Any] = field(default_factory=dict)
    state: str = "queued"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    message: str = ""
    progress: int = 0
    attempts: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "song_id": self.song_id,
            "stage": self.stage,
            "params": self.params,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message": self.message,
            "progress": self.progress,
            "attempts": self.attempts,
        }


class LocalJobRunner:
    def __init__(self, library: LibraryPaths, pipeline: Pipeline) -> None:
        self.library = library
        self.pipeline = pipeline
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, name="ktv-job-runner", daemon=True)
        self._started = False
        self._state_lock = threading.Lock()

    def start(self) -> None:
        self.library.jobs_root.mkdir(parents=True, exist_ok=True)
        self._recover_jobs()
        if not self._started:
            self._thread.start()
            self._started = True

    def submit(self, song_id: str, stage: str, params: dict[str, Any] | None = None) -> Job:
        clean_id = normalize_song_id(song_id)
        self.library.ensure_song_dirs(clean_id)
        job = Job(
            job_id=uuid.uuid4().hex,
            song_id=clean_id,
            stage=stage,
            params=params or {},
        )
        self._save(job)
        append_stage_status(self.library.status_json(job.song_id), stage, "queued", f"job {job.job_id}")
        self._queue.put(job.job_id)
        return job

    def cancel(self, job_id: str) -> bool:
        job = self._load(job_id)
        if job is None:
            return False
        if job.state != "queued":
            job.message = "Only queued jobs can be canceled."
            self._save(job)
            return False
        job.state = "canceled"
        job.message = "canceled before start"
        job.progress = 0
        self._save(job)
        append_stage_status(self.library.status_json(job.song_id), job.stage, "canceled", f"job {job.job_id}")
        return True

    def retry(self, job_id: str) -> Job | None:
        job = self._load(job_id)
        if job is None or job.state not in {"failed", "canceled"}:
            return None
        return self.submit(job.song_id, job.stage, {**job.params, "retry_of": job.job_id})

    def list_jobs(self, *, limit: int = 25) -> list[Job]:
        if not self.library.jobs_root.exists():
            return []
        jobs: list[Job] = []
        for path in self.library.jobs_root.glob("*.json"):
            data = read_json(path, default=None)
            if isinstance(data, dict):
                jobs.append(self._with_progress(Job.from_dict(data)))
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs[:limit]

    def _recover_jobs(self) -> None:
        for job in reversed(self.list_jobs(limit=1000)):
            if job.state in {"queued", "running"}:
                job.state = "queued"
                job.message = "recovered after app start"
                job.updated_at = utc_now()
                self._save(job)
                self._queue.put(job.job_id)

    def _load(self, job_id: str) -> Job | None:
        data = read_json(self.library.job_json(job_id), default=None)
        return Job.from_dict(data) if isinstance(data, dict) else None

    def _save(self, job: Job) -> None:
        with self._state_lock:
            job.updated_at = utc_now()
            write_json(self.library.job_json(job.job_id), job.to_dict())

    def _with_progress(self, job: Job) -> Job:
        job.progress = estimate_stage_progress(self.library, job.song_id, job.stage, job.state)
        return job

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                job = self._load(job_id)
                if job is None:
                    continue
                if job.state == "canceled":
                    continue
                self._run(job)
            finally:
                self._queue.task_done()

    def _run(self, job: Job) -> None:
        job.state = "running"
        job.message = ""
        job.attempts += 1
        job.progress = 5
        self._save(job)
        try:
            run_pipeline_stage(self.pipeline, job)
        except Exception as exc:
            job.state = "failed"
            job.message = str(exc)
            self._save(job)
            append_stage_status(self.library.status_json(job.song_id), job.stage, "failed", str(exc))
            return
        job.state = "completed"
        job.message = "completed"
        job.progress = 100
        self._save(job)


def run_pipeline_stage(pipeline: Pipeline, job: Job) -> None:
    params = job.params
    if job.stage == "probe":
        pipeline.probe(job.song_id)
    elif job.stage == "extract":
        pipeline.extract(job.song_id, audio_index=int(params.get("audio_index", 0)))
    elif job.stage == "preview-tracks":
        pipeline.preview_tracks(job.song_id, duration=float(params.get("duration", 20.0)))
    elif job.stage == "separate":
        pipeline.separate(job.song_id)
    elif job.stage == "align":
        pipeline.align(job.song_id)
    elif job.stage == "shift-subtitles":
        pipeline.shift_subtitles(job.song_id, seconds=float(params.get("seconds", 0.0)))
    elif job.stage == "edit-subtitles":
        pipeline.edit_subtitles(job.song_id, list(params.get("updates") or []))
    elif job.stage == "mux":
        pipeline.mux(job.song_id, audio_order=str(params.get("audio_order", "instrumental-first")))
    elif job.stage == "replace-audio":
        pipeline.replace_audio(job.song_id, keep_audio_index=int(params.get("keep_audio_index", 0)))
    elif job.stage == "clean-work":
        pipeline.clean_work(job.song_id)
    elif job.stage == "process":
        pipeline.process(job.song_id)
    else:
        raise ValueError(f"unknown stage: {job.stage}")
