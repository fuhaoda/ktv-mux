import traceback
from pathlib import Path

from .diagnostics import run_doctor
from .errors import KtvError
from .jobs import LocalJobRunner
from .jsonio import read_json
from .library import delete_song, record_imported_source, save_lyrics_text, song_summary
from .paths import LibraryPaths, derive_song_id_from_source, is_url, normalize_song_id
from .pipeline import Pipeline
from .versions import delete_take, list_takes, set_current_take, update_take
from .views import page, render_delete_confirm, render_detail, render_doctor, render_error, render_index, song_url
from .waveform import wav_waveform_svg


def create_app(library: LibraryPaths | None = None):
    try:
        from fastapi import FastAPI, File, Form, Request, Response, UploadFile
        from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
        from fastapi.staticfiles import StaticFiles
    except Exception as exc:  # pragma: no cover - exercised by CLI users without web extras.
        raise RuntimeError('Web UI dependencies are missing. Install with: pip install -e ".[web]"') from exc

    library = library or LibraryPaths()
    pipeline = Pipeline(library)
    runner = LocalJobRunner(library, pipeline)
    runner.start()
    app = FastAPI(title="ktv-mux")
    app.mount("/static", StaticFiles(directory=str(Path(__file__).with_name("static"))), name="static")

    @app.exception_handler(Exception)
    async def friendly_exception_handler(request: Request, exc: Exception):
        body = render_error(str(exc), traceback.format_exc(limit=8))
        return HTMLResponse(page("Error", body), status_code=500)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        songs = [song_summary(library, song_id) for song_id in library.list_song_ids()]
        jobs = [job.to_dict() for job in runner.list_jobs(limit=8)]
        auto_refresh = any(job.get("state") in {"queued", "running", "canceling"} for job in jobs)
        return page("Songs", render_index(songs, jobs), auto_refresh=auto_refresh)

    @app.get("/doctor", response_class=HTMLResponse)
    def doctor() -> str:
        return page("Doctor", render_doctor(run_doctor(library)))

    @app.post("/import")
    def import_route(
        source: str = Form(...),
        song_id: str = Form(""),
        title: str = Form(""),
        artist: str = Form(""),
    ):
        if is_url(source):
            clean_id = normalize_song_id(song_id) if song_id else derive_song_id_from_source(source)
            runner.submit(
                clean_id,
                "import-url",
                {"source": source, "title": title or "", "artist": artist or ""},
            )
            return RedirectResponse(song_url(clean_id), status_code=303)
        song = pipeline.import_source(
            source,
            song_id=song_id or None,
            title=title or None,
            artist=artist or None,
        )
        return RedirectResponse(song_url(song.song_id), status_code=303)

    @app.post("/import-upload")
    async def import_upload_route(
        file: UploadFile = File(...),
        song_id: str = Form(""),
        title: str = Form(""),
        artist: str = Form(""),
    ):
        original_name = file.filename or "upload.media"
        clean_id = normalize_song_id(song_id) if song_id else normalize_song_id(Path(original_name).stem)
        library.ensure_song_dirs(clean_id)
        suffix = Path(original_name).suffix.lower() or ".media"
        dest = library.raw_dir(clean_id) / f"source{suffix}"
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        song = record_imported_source(
            library,
            clean_id,
            dest,
            title=title or None,
            artist=artist or None,
        )
        return RedirectResponse(song_url(song.song_id), status_code=303)

    @app.get("/songs/{song_id}", response_class=HTMLResponse)
    def detail(song_id: str) -> str:
        clean_id = normalize_song_id(song_id)
        summary = song_summary(library, clean_id)
        status = read_json(library.status_json(clean_id), default={}) or {}
        report = read_json(library.report_json(clean_id), default={}) or {}
        lyrics = library.lyrics_txt(clean_id).read_text(encoding="utf-8") if library.lyrics_txt(clean_id).exists() else ""
        ass = library.lyrics_ass(clean_id).read_text(encoding="utf-8") if library.lyrics_ass(clean_id).exists() else ""
        alignment = read_json(library.alignment_json(clean_id), default={}) or {}
        jobs = [job.to_dict() for job in runner.list_jobs(limit=20) if job.song_id == clean_id]
        auto_refresh = status.get("state") in {"queued", "running", "canceling"} or any(
            job.get("state") in {"queued", "running", "canceling"} for job in jobs
        )
        body = render_detail(
            clean_id,
            summary,
            status,
            report,
            lyrics,
            ass,
            alignment,
            available_logs(library, clean_id),
            jobs,
            run_doctor(library, clean_id),
            list_takes(library, clean_id),
        )
        return page(clean_id, body, auto_refresh=auto_refresh)

    @app.post("/songs/{song_id}/lyrics")
    def save_lyrics(song_id: str, lyrics: str = Form("")):
        save_lyrics_text(library, song_id, lyrics)
        return RedirectResponse(song_url(song_id), status_code=303)

    @app.post("/songs/{song_id}/lyrics-file")
    async def upload_lyrics(song_id: str, file: UploadFile = File(...)):
        data = await file.read()
        save_lyrics_text(library, song_id, data.decode("utf-8-sig"))
        return RedirectResponse(song_url(song_id), status_code=303)

    @app.post("/songs/{song_id}/alignment")
    async def save_alignment(song_id: str, request: Request):
        clean_id = normalize_song_id(song_id)
        form = await request.form()
        updates = []
        line_count = int(form.get("line_count") or 0)
        for index in range(line_count):
            updates.append(
                {
                    "index": index,
                    "start": form.get(f"line_{index}_start"),
                    "end": form.get(f"line_{index}_end"),
                    "text": form.get(f"line_{index}_text"),
                }
            )
        runner.submit(clean_id, "edit-subtitles", {"updates": updates})
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/run/{stage}")
    def run_stage(
        song_id: str,
        stage: str,
        audio_index: int = Form(0),
        keep_audio_index: int = Form(0),
        audio_order: str = Form("instrumental-first"),
        preview_start: float = Form(0.0),
        preview_duration: float = Form(20.0),
    ):
        clean_id = normalize_song_id(song_id)
        if stage not in {
            "probe",
            "preview-tracks",
            "extract",
            "separate",
            "align",
            "mux",
            "replace-audio",
            "clean-work",
            "process",
        }:
            return PlainTextResponse(f"Unknown stage: {stage}", status_code=400)
        runner.submit(
            clean_id,
            stage,
            {
                "audio_index": audio_index,
                "keep_audio_index": keep_audio_index,
                "audio_order": audio_order,
                "start": preview_start,
                "duration": preview_duration,
            },
        )
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        runner.cancel(job_id)
        return RedirectResponse("/", status_code=303)

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str):
        job = runner.retry(job_id)
        location = song_url(job.song_id) if job else "/"
        return RedirectResponse(location, status_code=303)

    @app.post("/songs/{song_id}/shift")
    def shift_subtitles(song_id: str, seconds: float = Form(...)):
        clean_id = normalize_song_id(song_id)
        runner.submit(clean_id, "shift-subtitles", {"seconds": seconds})
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/take/{filename}/update")
    def update_take_route(song_id: str, filename: str, label: str = Form(""), note: str = Form("")):
        clean_id = normalize_song_id(song_id)
        update_take(library, clean_id, filename, label=label, note=note)
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/take/{filename}/set-current")
    def set_current_take_route(song_id: str, filename: str):
        clean_id = normalize_song_id(song_id)
        set_current_take(library, clean_id, filename)
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/take/{filename}/delete")
    def delete_take_route(song_id: str, filename: str):
        clean_id = normalize_song_id(song_id)
        delete_take(library, clean_id, filename)
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/delete")
    def delete_route(song_id: str, confirm: str = Form("")):
        clean_id = normalize_song_id(song_id)
        if confirm != clean_id:
            return HTMLResponse(
                page("Confirm Delete", render_delete_confirm(clean_id)),
                status_code=400,
            )
        delete_song(library, clean_id)
        return RedirectResponse("/", status_code=303)

    @app.get("/songs/{song_id}/audio/{kind}")
    def audio(song_id: str, kind: str):
        clean_id = normalize_song_id(song_id)
        try:
            path = audio_path(library, clean_id, kind)
        except KtvError:
            return PlainTextResponse("Audio not found", status_code=404)
        if not path.exists():
            return PlainTextResponse("Audio not found", status_code=404)
        return FileResponse(path, filename=path.name)

    @app.get("/songs/{song_id}/waveform.svg")
    def waveform(song_id: str):
        clean_id = normalize_song_id(song_id)
        path = library.instrumental_wav(clean_id) if library.instrumental_wav(clean_id).exists() else library.mix_wav(clean_id)
        return Response(wav_waveform_svg(path), media_type="image/svg+xml")

    @app.get("/songs/{song_id}/download/{kind}")
    def download(song_id: str, kind: str):
        clean_id = normalize_song_id(song_id)
        if kind == "ktv-mkv":
            path = library.final_mkv(clean_id)
        elif kind == "audio-replaced-mkv":
            path = library.audio_replaced_mkv(clean_id)
        elif kind.startswith("take/"):
            filename = Path(kind.split("/", 1)[1]).name
            path = library.takes_dir(clean_id) / filename
        elif kind in {"instrumental", "mix", "vocals"}:
            path = audio_path(library, clean_id, kind)
        else:
            return PlainTextResponse("Download not found", status_code=404)
        if not path.exists():
            return PlainTextResponse("File not found", status_code=404)
        return FileResponse(path, filename=path.name)

    @app.get("/songs/{song_id}/download/take/{filename}")
    def download_take(song_id: str, filename: str):
        clean_id = normalize_song_id(song_id)
        path = library.takes_dir(clean_id) / Path(filename).name
        if not path.exists():
            return PlainTextResponse("File not found", status_code=404)
        return FileResponse(path, filename=path.name)

    @app.get("/songs/{song_id}/log/{stage}", response_class=PlainTextResponse)
    def stage_log(song_id: str, stage: str):
        clean_id = normalize_song_id(song_id)
        path = library.stage_log(clean_id, stage)
        if not path.exists():
            return PlainTextResponse("No log yet.", status_code=404)
        return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace")[-12000:])

    return app


def serve(*, library: LibraryPaths, host: str, port: int) -> None:
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover
        raise RuntimeError('uvicorn is missing. Install with: pip install -e ".[web]"') from exc
    uvicorn.run(create_app(library), host=host, port=port)


def audio_path(library: LibraryPaths, song_id: str, kind: str) -> Path:
    if kind == "instrumental":
        return library.instrumental_wav(song_id)
    if kind == "mix":
        return library.mix_wav(song_id)
    if kind == "vocals":
        return library.vocals_wav(song_id)
    if kind.startswith("track-preview-"):
        try:
            index = int(kind.removeprefix("track-preview-")) - 1
        except ValueError as exc:
            raise KtvError(f"unknown audio kind: {kind}") from exc
        return library.track_preview_wav(song_id, index)
    raise KtvError(f"unknown audio kind: {kind}")


def available_logs(library: LibraryPaths, song_id: str) -> list[str]:
    logs_dir = library.work_dir(song_id) / "logs"
    if not logs_dir.exists():
        return []
    return sorted(path.stem for path in logs_dir.glob("*.log") if path.is_file())
