import asyncio
import json
import platform
import subprocess
import traceback
from pathlib import Path

from .checkpoints import stage_checkpoint_completed
from .diagnostics import run_doctor
from .errors import KtvError
from .exporter import export_song_package
from .jobs import LocalJobRunner
from .jsonio import read_json
from .library import (
    delete_song,
    import_inbox,
    record_imported_source,
    rename_song,
    save_lyrics_file,
    save_lyrics_text,
    song_summary,
    update_song_metadata,
)
from .paths import LibraryPaths, derive_song_id_from_source, is_url, normalize_song_id
from .pipeline import Pipeline
from .planner import next_actions
from .settings import load_settings, save_settings
from .storage import library_storage_report
from .versions import delete_take, list_takes, set_current_take, update_take
from .views import (
    page,
    render_delete_confirm,
    render_detail,
    render_doctor,
    render_error,
    render_import_confirm,
    render_index,
    render_job_detail,
    render_roadmap,
    render_settings,
    render_storage,
    render_wizard,
    song_url,
)
from .waveform import wav_waveform_svg


def create_app(library: LibraryPaths | None = None):
    try:
        from fastapi import FastAPI, File, Form, Request, Response, UploadFile
        from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
        from fastapi.staticfiles import StaticFiles
    except Exception as exc:  # pragma: no cover - exercised by CLI users without web extras.
        raise RuntimeError('Web UI dependencies are missing. Install with: pip install -e ".[web]"') from exc

    library = library or LibraryPaths()
    pipeline = Pipeline(library)
    settings = load_settings(library)
    runner = LocalJobRunner(library, pipeline, worker_count=int(settings["worker_count"]))
    runner.start()
    app = FastAPI(title="ktv-mux")
    app.mount("/static", StaticFiles(directory=str(Path(__file__).with_name("static"))), name="static")

    @app.exception_handler(Exception)
    async def friendly_exception_handler(request: Request, exc: Exception):
        body = render_error(str(exc), traceback.format_exc(limit=8))
        return HTMLResponse(page("Error", body), status_code=500)

    @app.get("/", response_class=HTMLResponse)
    def index(q: str = "", file_filter: str = "") -> str:
        settings = load_settings(library)
        songs = _filter_songs(
            [song_summary(library, song_id) for song_id in library.list_song_ids()],
            query=q,
            file_filter=file_filter,
        )
        jobs = [job.to_dict() for job in runner.list_jobs(limit=8)]
        auto_refresh = any(job.get("state") in {"queued", "running", "canceling"} for job in jobs)
        return page(
            "Songs",
            render_index(
                songs,
                jobs,
                query=q,
                file_filter=file_filter,
                inbox_files=[path.name for path in sorted(library.inbox_dir.glob("*")) if path.is_file()]
                if library.inbox_dir.exists()
                else [],
                storage=library_storage_report(library),
            ),
            auto_refresh=auto_refresh,
            refresh_seconds=int(settings["auto_refresh_seconds"]),
        )

    @app.get("/wizard", response_class=HTMLResponse)
    def wizard() -> str:
        songs = [song_summary(library, song_id) for song_id in library.list_song_ids()]
        return page("First Run Wizard", render_wizard(run_doctor(library), songs, load_settings(library)))

    @app.post("/sample/import")
    def import_sample():
        sample = Path(__file__).resolve().parents[2] / "assets" / "朋友-周华健.mkv"
        if not sample.exists():
            raise KtvError(f"sample asset not found: {sample}")
        song = pipeline.import_source(str(sample), title="朋友", artist="周华健")
        if not library.lyrics_txt(song.song_id).exists():
            save_lyrics_text(library, song.song_id, "朋友一生一起走\n那些日子不再有\n一句话一辈子\n一生情一杯酒\n")
        return RedirectResponse(song_url(song.song_id), status_code=303)

    @app.get("/doctor", response_class=HTMLResponse)
    def doctor() -> str:
        return page("Doctor", render_doctor(run_doctor(library)))

    @app.get("/storage", response_class=HTMLResponse)
    def storage_page() -> str:
        return page("Storage", render_storage(library_storage_report(library)))

    @app.get("/roadmap", response_class=HTMLResponse)
    def roadmap_page() -> str:
        return page("Roadmap", render_roadmap())

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page() -> str:
        return page("Settings", render_settings(load_settings(library)))

    @app.post("/settings")
    def settings_save(
        worker_count: int = Form(2),
        preview_start: float = Form(0.0),
        preview_duration: float = Form(20.0),
        preview_count: int = Form(1),
        preview_spacing: float = Form(45.0),
        preview_preset: str = Form("manual"),
        demucs_model: str = Form("htdemucs"),
        demucs_device: str = Form("auto"),
        normalize_target_i: float = Form(-16.0),
        auto_refresh_seconds: int = Form(3),
        default_audio_order: str = Form("instrumental-first"),
        default_duration_limit: float = Form(0.0),
        output_template: str = Form("{song_id}.ktv.mkv"),
        package_include_logs: str = Form(""),
        subtitle_font_size: int = Form(48),
        subtitle_margin_v: int = Form(58),
        subtitle_primary_colour: str = Form("&H00FFFFFF"),
        subtitle_secondary_colour: str = Form("&H0000D7FF"),
        instrumental_track_title: str = Form("伴奏"),
        original_track_title: str = Form("原唱"),
    ):
        save_settings(
            library,
            {
                "worker_count": worker_count,
                "preview_start": preview_start,
                "preview_duration": preview_duration,
                "preview_count": preview_count,
                "preview_spacing": preview_spacing,
                "preview_preset": preview_preset,
                "demucs_model": demucs_model,
                "demucs_device": demucs_device,
                "normalize_target_i": normalize_target_i,
                "auto_refresh_seconds": auto_refresh_seconds,
                "default_audio_order": default_audio_order,
                "default_duration_limit": default_duration_limit,
                "output_template": output_template,
                "package_include_logs": bool(package_include_logs),
                "subtitle_font_size": subtitle_font_size,
                "subtitle_margin_v": subtitle_margin_v,
                "subtitle_primary_colour": subtitle_primary_colour,
                "subtitle_secondary_colour": subtitle_secondary_colour,
                "instrumental_track_title": instrumental_track_title,
                "original_track_title": original_track_title,
            },
        )
        return RedirectResponse("/settings", status_code=303)

    @app.post("/import")
    def import_route(
        source: str = Form(...),
        song_id: str = Form(""),
        title: str = Form(""),
        artist: str = Form(""),
        rights: str = Form(""),
        confirm: str = Form(""),
    ):
        if is_url(source):
            if confirm != "1" or rights != "1":
                return HTMLResponse(page("Confirm URL Import", render_import_confirm(source, song_id, title, artist)))
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

    @app.post("/inbox-scan")
    def inbox_scan():
        import_inbox(library, pipeline)
        return RedirectResponse("/", status_code=303)

    @app.post("/batch-stage")
    def batch_stage_route(
        stage: str = Form("probe"),
        limit: int = Form(0),
        skip_completed: str = Form(""),
        stop_on_error: str = Form(""),
        dry_run: str = Form(""),
        audio_index: int = Form(0),
        separation_preset: str = Form("balanced"),
    ):
        if stage not in {"probe", "preview-tracks", "extract", "separate", "separate-sample"}:
            return PlainTextResponse(f"Unknown stage: {stage}", status_code=400)
        if dry_run:
            pipeline.batch_stage(
                stage,
                limit=limit,
                skip_completed=bool(skip_completed),
                stop_on_error=bool(stop_on_error),
                dry_run=True,
                audio_index=audio_index,
                separation_preset=separation_preset,
            )
            return RedirectResponse("/", status_code=303)
        submitted = 0
        for song_id in library.list_song_ids():
            if limit and submitted >= limit:
                break
            if skip_completed and stage_checkpoint_completed(library, song_id, stage):
                continue
            runner.submit(song_id, stage, {"audio_index": audio_index, "separation_preset": separation_preset})
            submitted += 1
            if stop_on_error:
                break
        return RedirectResponse("/", status_code=303)

    @app.post("/batch-recipe")
    def batch_recipe_route(
        recipe: str = Form("instrumental-review"),
        audio_index: int = Form(0),
        separation_preset: str = Form("fast-review"),
        dry_run: str = Form(""),
    ):
        plan = pipeline.batch_recipe(
            recipe,
            dry_run=True,
            audio_index=audio_index,
            separation_preset=separation_preset,
        )
        if dry_run:
            return PlainTextResponse(json.dumps(plan, ensure_ascii=False, indent=2), status_code=200)
        for song in plan.get("songs") or []:
            song_id = str(song.get("song_id") or "")
            for stage in song.get("stages") or []:
                runner.submit(song_id, str(stage), {"audio_index": audio_index, "separation_preset": separation_preset})
        return RedirectResponse("/", status_code=303)

    @app.get("/events")
    async def events():
        async def stream():
            for _ in range(30):
                jobs = [job.to_dict() for job in runner.list_jobs(limit=25)]
                yield "event: jobs\n"
                yield f"data: {json.dumps({'jobs': jobs}, ensure_ascii=False)}\n\n"
                if not any(job.get("state") in {"queued", "running", "canceling"} for job in jobs):
                    break
                await asyncio.sleep(1)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/import-upload")
    async def import_upload_route(
        files: list[UploadFile] = File(...),
        song_id: str = Form(""),
        title: str = Form(""),
        artist: str = Form(""),
    ):
        songs = []
        for index, file in enumerate(files):
            songs.append(
                await save_upload(
                    library,
                    file,
                    song_id=song_id if len(files) == 1 else "",
                    title=title if index == 0 else "",
                    artist=artist if index == 0 else "",
                )
            )
        location = song_url(songs[0].song_id) if len(songs) == 1 else "/"
        return RedirectResponse(location, status_code=303)

    @app.get("/songs/{song_id}", response_class=HTMLResponse)
    def detail(song_id: str) -> str:
        clean_id = normalize_song_id(song_id)
        settings = load_settings(library)
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
            next_actions(library, clean_id),
            settings,
            log_tails(library, clean_id),
        )
        return page(clean_id, body, auto_refresh=auto_refresh, refresh_seconds=int(settings["auto_refresh_seconds"]))

    @app.post("/songs/{song_id}/metadata")
    def save_metadata(
        song_id: str,
        title: str = Form(""),
        artist: str = Form(""),
        tags: str = Form(""),
        rating: str = Form(""),
    ):
        clean_id = normalize_song_id(song_id)
        parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        update_song_metadata(
            library,
            clean_id,
            title=title or None,
            artist=artist or None,
            tags=parsed_tags,
            rating=int(rating) if rating else None,
        )
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/rename")
    def rename_song_route(song_id: str, new_song_id: str = Form("")):
        song = rename_song(library, song_id, new_song_id)
        return RedirectResponse(song_url(song.song_id), status_code=303)

    @app.post("/songs/{song_id}/lyrics")
    def save_lyrics(song_id: str, lyrics: str = Form("")):
        save_lyrics_text(library, song_id, lyrics)
        return RedirectResponse(song_url(song_id), status_code=303)

    @app.post("/songs/{song_id}/lyrics-file")
    async def upload_lyrics(song_id: str, file: UploadFile = File(...)):
        data = await file.read()
        temp = library.raw_dir(song_id) / (file.filename or "lyrics.txt")
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(data)
        save_lyrics_file(library, song_id, temp)
        return RedirectResponse(song_url(song_id), status_code=303)

    @app.post("/songs/{song_id}/instrumental-file")
    async def upload_instrumental(
        song_id: str,
        file: UploadFile = File(...),
        label: str = Form("external instrumental"),
        offset: float = Form(0.0),
        gain_db: float = Form(0.0),
        fit_to_mix: str = Form(""),
        normalize: str = Form(""),
    ):
        clean_id = normalize_song_id(song_id)
        temp = library.output_dir(clean_id) / f"uploaded-{Path(file.filename or 'instrumental.wav').name}"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(await file.read())
        pipeline.set_instrumental(
            clean_id,
            temp,
            label=label or "external instrumental",
            offset=offset,
            gain_db=gain_db,
            fit_to_mix=bool(fit_to_mix),
            normalize=bool(normalize),
        )
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/track-role")
    def save_track_role(
        song_id: str,
        audio_index: int = Form(0),
        role: str = Form("unknown"),
        note: str = Form(""),
    ):
        clean_id = normalize_song_id(song_id)
        pipeline.set_track_role(clean_id, audio_index=audio_index, role=role, note=note)
        return RedirectResponse(song_url(clean_id), status_code=303)

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

    @app.post("/songs/{song_id}/alignment-shift-lines")
    def shift_subtitle_lines(song_id: str, start_line: int = Form(1), end_line: int = Form(1), seconds: float = Form(0.0)):
        clean_id = normalize_song_id(song_id)
        runner.submit(
            clean_id,
            "shift-subtitle-lines",
            {"start_line": start_line, "end_line": end_line, "seconds": seconds},
        )
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/alignment-stretch-lines")
    def stretch_subtitle_lines(
        song_id: str,
        start_line: int = Form(1),
        end_line: int = Form(1),
        target_start: float = Form(0.0),
        target_end: float = Form(1.0),
    ):
        clean_id = normalize_song_id(song_id)
        runner.submit(
            clean_id,
            "stretch-subtitle-lines",
            {
                "start_line": start_line,
                "end_line": end_line,
                "target_start": target_start,
                "target_end": target_end,
            },
        )
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
        preview_count: int = Form(1),
        preview_spacing: float = Form(45.0),
        preview_preset: str = Form("manual"),
        separation_preset: str = Form("balanced"),
        model: str = Form(""),
        device: str = Form("auto"),
        target_i: float = Form(-16.0),
        replace_current: str = Form(""),
        copy_subtitles: str = Form(""),
        subtitle_index: int = Form(0),
        start_stage: str = Form("probe"),
        align_backend: str = Form("auto"),
        duration_limit: float = Form(0.0),
        force: str = Form(""),
    ):
        clean_id = normalize_song_id(song_id)
        if stage not in {
            "probe",
            "preview-tracks",
            "extract",
            "separate",
            "separate-sample",
            "align",
            "extract-subtitles",
            "mux",
            "replace-audio",
            "remake-track",
            "normalize",
            "clean-work",
            "process",
            "process-from",
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
                "count": preview_count,
                "spacing": preview_spacing,
                "preset": preview_preset,
                "separation_preset": separation_preset,
                "model": model or None,
                "device": device,
                "target_i": target_i,
                "replace_current": bool(replace_current),
                "copy_subtitles": bool(copy_subtitles),
                "subtitle_index": subtitle_index,
                "start_stage": start_stage,
                "align_backend": align_backend,
                "duration_limit": duration_limit or None,
                "force": bool(force),
            },
        )
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        runner.cancel(job_id)
        return RedirectResponse("/", status_code=303)

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_detail(job_id: str) -> str:
        job = runner.get_job(job_id)
        if job is None:
            return HTMLResponse(page("Job not found", render_error("Job not found", "")), status_code=404)
        return page(f"Job {job.job_id[:8]}", render_job_detail(job.to_dict(), log_tails(library, job.song_id)))

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str):
        job = runner.retry(job_id)
        location = song_url(job.song_id) if job else "/"
        return RedirectResponse(location, status_code=303)

    @app.post("/jobs/prune")
    def prune_jobs_route():
        runner.prune_jobs()
        return RedirectResponse("/", status_code=303)

    @app.post("/songs/{song_id}/shift")
    def shift_subtitles(song_id: str, seconds: float = Form(...)):
        clean_id = normalize_song_id(song_id)
        runner.submit(clean_id, "shift-subtitles", {"seconds": seconds})
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.post("/songs/{song_id}/take/{filename}/update")
    def update_take_route(song_id: str, filename: str, label: str = Form(""), note: str = Form(""), score: str = Form("")):
        clean_id = normalize_song_id(song_id)
        update_take(library, clean_id, filename, label=label, note=note, score=int(score) if score else None)
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

    @app.get("/songs/{song_id}/export")
    def export_song(
        song_id: str,
        include_audio: bool = True,
        include_mkv: bool = True,
        include_takes: bool = True,
        include_logs: bool = False,
    ):
        clean_id = normalize_song_id(song_id)
        path = export_song_package(
            library,
            clean_id,
            include_audio=include_audio,
            include_mkv=include_mkv,
            include_takes=include_takes,
            include_logs=include_logs,
        )
        return FileResponse(path, filename=path.name)

    @app.get("/songs/{song_id}/reveal/{kind}")
    def reveal(song_id: str, kind: str):
        clean_id = normalize_song_id(song_id)
        path = output_path(library, clean_id, kind)
        if path.exists() and platform.system() == "Darwin":
            subprocess.run(["open", "-R", str(path)], check=False)
        return RedirectResponse(song_url(clean_id), status_code=303)

    @app.get("/songs/{song_id}/download/{kind}")
    def download(song_id: str, kind: str):
        clean_id = normalize_song_id(song_id)
        if kind == "ktv-mkv":
            path = library.final_mkv(clean_id)
        elif kind == "audio-replaced-mkv":
            path = library.audio_replaced_mkv(clean_id)
        elif kind == "templated-final-mkv":
            report = read_json(library.report_json(clean_id), default={}) or {}
            path = Path(str(report.get("templated_final_mkv") or ""))
        elif kind.startswith("take/"):
            filename = Path(kind.split("/", 1)[1]).name
            path = library.takes_dir(clean_id) / filename
        elif kind in {"instrumental", "instrumental-normalized", "instrumental-sample", "mix", "vocals", "vocals-sample"}:
            path = audio_path(library, clean_id, kind)
        else:
            return PlainTextResponse("Download not found", status_code=404)
        if not path.exists() or not path.is_file():
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


async def save_upload(
    library: LibraryPaths,
    file,
    *,
    song_id: str = "",
    title: str = "",
    artist: str = "",
):
    original_name = file.filename or "upload.media"
    clean_id = normalize_song_id(song_id) if song_id else normalize_song_id(Path(original_name).stem)
    library.ensure_song_dirs(clean_id)
    suffix = Path(original_name).suffix.lower() or ".media"
    dest = library.raw_dir(clean_id) / f"source{suffix}"
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    return record_imported_source(
        library,
        clean_id,
        dest,
        title=title or None,
        artist=artist or None,
    )


def audio_path(library: LibraryPaths, song_id: str, kind: str) -> Path:
    if kind == "instrumental":
        return library.instrumental_wav(song_id)
    if kind == "instrumental-normalized":
        return library.normalized_instrumental_wav(song_id)
    if kind == "instrumental-sample":
        return library.instrumental_sample_wav(song_id)
    if kind == "mix":
        return library.mix_wav(song_id)
    if kind == "vocals":
        return library.vocals_wav(song_id)
    if kind == "vocals-sample":
        return library.vocals_sample_wav(song_id)
    if kind.startswith("track-preview-"):
        try:
            parts = kind.removeprefix("track-preview-").split("-")
            index = int(parts[0]) - 1
            segment = int(parts[1]) - 1 if len(parts) > 1 else 0
        except ValueError as exc:
            raise KtvError(f"unknown audio kind: {kind}") from exc
        return library.track_preview_wav(song_id, index, segment)
    raise KtvError(f"unknown audio kind: {kind}")


def output_path(library: LibraryPaths, song_id: str, kind: str) -> Path:
    if kind == "ktv-mkv":
        return library.final_mkv(song_id)
    if kind == "audio-replaced-mkv":
        return library.audio_replaced_mkv(song_id)
    if kind in {"instrumental", "instrumental-normalized", "instrumental-sample", "mix", "vocals", "vocals-sample"}:
        return audio_path(library, song_id, kind)
    if kind == "lyrics-ass":
        return library.lyrics_ass(song_id)
    if kind == "report":
        return library.report_json(song_id)
    raise KtvError(f"unknown output kind: {kind}")


def available_logs(library: LibraryPaths, song_id: str) -> list[str]:
    logs_dir = library.work_dir(song_id) / "logs"
    if not logs_dir.exists():
        return []
    return sorted(path.stem for path in logs_dir.glob("*.log") if path.is_file())


def log_tails(library: LibraryPaths, song_id: str, *, limit: int = 5000) -> dict[str, str]:
    tails: dict[str, str] = {}
    for stage in available_logs(library, song_id):
        path = library.stage_log(song_id, stage)
        tails[stage] = path.read_text(encoding="utf-8", errors="replace")[-limit:]
    return tails


def _filter_songs(songs: list[dict[str, object]], *, query: str = "", file_filter: str = "") -> list[dict[str, object]]:
    query = query.strip().lower()
    filtered = []
    flag_map = {
        "source": "has_source",
        "lyrics": "has_lyrics",
        "instrumental": "has_instrumental",
        "ktv-mkv": "has_mkv",
    }
    required_flag = flag_map.get(file_filter)
    for song in songs:
        if required_flag and not song.get(required_flag):
            continue
        haystack = " ".join(str(song.get(key) or "") for key in ["song_id", "title", "artist", "tags"]).lower()
        if query and query not in haystack:
            continue
        filtered.append(song)
    return filtered
