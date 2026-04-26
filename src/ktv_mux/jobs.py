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
    def __init__(self, library: LibraryPaths, pipeline: Pipeline, *, worker_count: int = 2) -> None:
        self.library = library
        self.pipeline = pipeline
        self._queue: queue.Queue[str] = queue.Queue()
        self._worker_count = max(1, worker_count)
        self._threads = [
            threading.Thread(target=self._worker, name=f"ktv-job-runner-{index + 1}", daemon=True)
            for index in range(self._worker_count)
        ]
        self._started = False
        self._state_lock = threading.Lock()

    def start(self) -> None:
        self.library.jobs_root.mkdir(parents=True, exist_ok=True)
        self._recover_jobs()
        if not self._started:
            for thread in self._threads:
                thread.start()
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
        if job.state == "queued":
            job.state = "canceled"
            job.message = "canceled before start"
            job.progress = 0
            self._save(job)
            append_stage_status(self.library.status_json(job.song_id), job.stage, "canceled", f"job {job.job_id}")
            return True
        if job.state in {"running", "canceling"}:
            cancel_file = self.library.job_cancel_file(job.job_id)
            cancel_file.parent.mkdir(parents=True, exist_ok=True)
            cancel_file.write_text(utc_now() + "\n", encoding="utf-8")
            job.state = "canceling"
            job.message = "cancel requested"
            self._save(job)
            append_stage_status(self.library.status_json(job.song_id), job.stage, "canceling", f"job {job.job_id}")
            return True
        job.message = f"Cannot cancel a {job.state} job."
        self._save(job)
        return False

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
            if job.state == "canceling":
                job.state = "canceled"
                job.message = "canceled after app restart"
                job.updated_at = utc_now()
                self._save(job)
                continue
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
        cancel_file = self.library.job_cancel_file(job.job_id)
        if cancel_file.exists():
            cancel_file.unlink()
        job.state = "running"
        job.message = ""
        job.attempts += 1
        job.progress = 5
        self._save(job)
        try:
            run_pipeline_stage(self.pipeline, job, cancel_file=cancel_file)
        except Exception as exc:
            canceled = cancel_file.exists() or "command canceled" in str(exc).lower()
            job.state = "canceled" if canceled else "failed"
            job.message = str(exc)
            job.progress = 0
            self._save(job)
            append_stage_status(self.library.status_json(job.song_id), job.stage, job.state, str(exc))
            if cancel_file.exists():
                cancel_file.unlink()
            return
        if cancel_file.exists():
            cancel_file.unlink()
        job.state = "completed"
        job.message = "completed"
        job.progress = 100
        self._save(job)


def run_pipeline_stage(pipeline: Pipeline, job: Job, *, cancel_file: Any | None = None) -> None:
    params = job.params
    if job.stage in {"import", "import-url"}:
        pipeline.import_source(
            str(params["source"]),
            song_id=job.song_id,
            title=params.get("title") or None,
            artist=params.get("artist") or None,
            cancel_file=cancel_file,
        )
    elif job.stage == "probe":
        pipeline.probe(job.song_id)
    elif job.stage == "extract":
        pipeline.extract(job.song_id, audio_index=int(params.get("audio_index", 0)), cancel_file=cancel_file)
    elif job.stage == "preview-tracks":
        pipeline.preview_tracks(
            job.song_id,
            duration=float(params.get("duration", 20.0)),
            start=float(params.get("start", 0.0)),
            cancel_file=cancel_file,
        )
    elif job.stage == "separate":
        pipeline.separate(job.song_id, model=str(params.get("model", "htdemucs")), cancel_file=cancel_file)
    elif job.stage == "align":
        pipeline.align(job.song_id, backend=str(params.get("backend", "auto")))
    elif job.stage == "shift-subtitles":
        pipeline.shift_subtitles(job.song_id, seconds=float(params.get("seconds", 0.0)))
    elif job.stage == "edit-subtitles":
        pipeline.edit_subtitles(job.song_id, list(params.get("updates") or []))
    elif job.stage == "mux":
        pipeline.mux(
            job.song_id,
            audio_order=str(params.get("audio_order", "instrumental-first")),
            cancel_file=cancel_file,
        )
    elif job.stage == "replace-audio":
        pipeline.replace_audio(
            job.song_id,
            keep_audio_index=int(params.get("keep_audio_index", 0)),
            copy_subtitles=bool(params.get("copy_subtitles", True)),
            cancel_file=cancel_file,
        )
    elif job.stage == "clean-work":
        pipeline.clean_work(job.song_id)
    elif job.stage == "process":
        pipeline.process(job.song_id, align_backend=str(params.get("align_backend", "auto")), cancel_file=cancel_file)
    else:
        raise ValueError(f"unknown stage: {job.stage}")
