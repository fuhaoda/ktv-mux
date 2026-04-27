from __future__ import annotations

from html import escape
from typing import Any

from .paths import normalize_song_id
from .view_common import fmt, fmt_attr, json_dump, render_select_options, song_url, trim


def render_jobs(jobs: list[dict[str, Any]]) -> str:
    if not jobs:
        return "<div class='empty'>No queued jobs.</div>"
    rows = []
    for job in jobs:
        state = str(job.get("state") or "")
        state_class = (
            "ok" if state == "completed" else "warn" if state in {"running", "queued", "canceling"} else "bad" if state == "failed" else ""
        )
        progress = int(job.get("progress") or 0)
        actions = render_job_actions(job)
        output_hint = job_output_hint(str(job.get("stage") or ""))
        rows.append(
            f"<tr><td>{escape(str(job.get('created_at') or ''))}</td>"
            f"<td class='compact'>{escape(str(job.get('updated_at') or ''))}</td>"
            f"<td><a href='{song_url(str(job.get('song_id') or ''))}'>{escape(str(job.get('song_id') or ''))}</a></td>"
            f"<td><a href='/jobs/{escape(str(job.get('job_id') or ''))}'>{escape(str(job.get('stage') or ''))}</a></td>"
            f"<td><span class='badge {state_class}'>{escape(state)}</span></td>"
            f"<td><div class='progress'><span style='width:{progress}%'></span></div><div class='compact'>{progress}%</div></td>"
            f"<td class='compact'>{escape(output_hint)}</td>"
            f"<td class='compact'>{escape(trim(str(job.get('message') or ''), 160))}</td>"
            f"<td>{actions}</td></tr>"
        )
    return f"<table><thead><tr><th>Created</th><th>Updated</th><th>Song</th><th>Stage</th><th>State</th><th>Progress</th><th>Output</th><th>Message</th><th>Actions</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"

def render_job_detail(job: dict[str, Any], log_tails: dict[str, str]) -> str:
    state = str(job.get("state") or "")
    state_class = (
        "ok" if state == "completed" else "warn" if state in {"running", "queued", "canceling"} else "bad" if state == "failed" else ""
    )
    stage = str(job.get("stage") or "")
    song_id = str(job.get("song_id") or "")
    log_text = log_tails.get(stage) or ""
    return f"""
<section class="hero">
  <div><h1>Job {escape(str(job.get("job_id") or "")[:8])}</h1><div class="subtle">{escape(song_id)} / {escape(stage)}</div></div>
  <span class="badge {state_class}">{escape(state)}</span>
</section>
<section class="grid-2">
  <div class="panel stack">
    <h2>Job Detail</h2>
    <div class="metric"><div>Progress</div><div>{fmt(job.get("progress"))}%</div><div>Attempts</div><div>{fmt(job.get("attempts"))}</div><div>Updated</div><div>{escape(str(job.get("updated_at") or ""))}</div></div>
    <div class="compact">{escape(trim(str(job.get("message") or ""), 800))}</div>
    <pre>{escape(json_dump(job.get("params") or {}))}</pre>
    <div class="row"><a class="button secondary" href="{song_url(song_id)}">Open Song</a>{render_job_actions(job)}</div>
  </div>
  <div class="panel">
    <h2>Stage Log Tail</h2>
    <pre>{escape(log_text or "No log for this stage yet.")}</pre>
  </div>
</section>
"""

def render_job_actions(job: dict[str, Any]) -> str:
    job_id = escape(str(job.get("job_id") or ""))
    state = str(job.get("state") or "")
    if state in {"queued", "running", "canceling"}:
        return f"<form class='mini-form' method='post' action='/jobs/{job_id}/cancel'><button class='secondary' type='submit'>Cancel</button></form>"
    if state in {"failed", "canceled"}:
        return f"<form class='mini-form' method='post' action='/jobs/{job_id}/retry'><button class='secondary' type='submit'>Retry</button></form>"
    return ""

def job_output_hint(stage: str) -> str:
    return {
        "probe": "report.json",
        "preview-tracks": "track preview WAVs",
        "extract": "mix.wav",
        "separate": "instrumental.wav, vocals.wav",
        "separate-sample": "sample instrumental WAV",
        "set-instrumental": "instrumental.wav",
        "extract-subtitles": "lyrics.txt, lyrics.ass",
        "remake-track": "instrumental.wav + audio-replaced MKV",
        "normalize": "instrumental.normalized.wav",
        "align": "alignment.json, lyrics.ass",
        "mux": "final KTV MKV",
        "replace-audio": "audio-replaced MKV",
        "process": "full pipeline outputs",
        "process-from": "remaining pipeline outputs",
    }.get(stage, "")

def render_logs(song_id: str, logs: list[str], log_tails: dict[str, str] | None = None) -> str:
    if not logs:
        return "<div class='empty'>No stage logs yet.</div>"
    links = "".join(
        f"<a class='button secondary' href='{song_url(song_id)}/log/{escape(stage)}' target='_blank'>{escape(stage)}.log</a>"
        for stage in logs
    )
    tails = ""
    for stage in logs:
        text = (log_tails or {}).get(stage)
        if text:
            tails += f"<h3>{escape(stage)}.log tail</h3><pre>{escape(text)}</pre>"
    return f"<div class='tight'><div class='row'>{links}</div>{tails}</div>"

def render_doctor_summary(doctor: dict[str, Any]) -> str:
    checks = doctor.get("checks") or []
    failed = [check for check in checks if not check.get("ok") and check.get("required")]
    optional = [check for check in checks if not check.get("ok") and not check.get("required")]
    badge = "ok" if not failed else "bad"
    body = f"<span class='badge {badge}'>{'ready' if not failed else 'attention needed'}</span>"
    if failed:
        body += "<div class='compact'>" + "; ".join(escape(str(item.get("name"))) for item in failed) + "</div>"
    if optional:
        body += "<div class='subtle'>Optional missing: " + ", ".join(escape(str(item.get("name"))) for item in optional) + "</div>"
    hint = ((doctor.get("song") or {}).get("next_hint") or "").strip()
    if hint:
        body += f"<div class='subtle'>{escape(hint)}</div>"
    body += "<div style='margin-top:8px;'><a class='button secondary' href='/doctor'>Open Doctor</a></div>"
    return body

def render_doctor(doctor: dict[str, Any]) -> str:
    rows = []
    for check in doctor.get("checks") or []:
        state = "ok" if check.get("ok") else "warn" if not check.get("required") else "bad"
        rows.append(
            f"<tr><td>{escape(str(check.get('name') or ''))}</td>"
            f"<td><span class='badge {state}'>{'ok' if check.get('ok') else 'missing'}</span></td>"
            f"<td>{escape(str(check.get('detail') or ''))}</td>"
            f"<td class='compact'>{escape(str(check.get('hint') or ''))}</td>"
            f"<td class='path'>{escape(str(check.get('fix') or ''))}</td></tr>"
        )
    return f"""
<section class="hero">
  <div><h1>Doctor</h1><div class="subtle">Dependency and library checks for the local KTV workflow.</div></div>
  <span class="badge {'ok' if doctor.get('ok') else 'bad'}">{'ready' if doctor.get('ok') else 'attention needed'}</span>
</section>
<section class="panel">
  <table>
    <thead><tr><th>Check</th><th>State</th><th>Detail</th><th>Hint</th><th>Fix Command</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
<section class="panel" style="margin-top:16px;">
  <h2>Library</h2>
  <pre>{escape(json_dump(doctor.get('library') or {}))}</pre>
</section>
"""

def render_wizard(doctor: dict[str, Any], songs: list[dict[str, Any]], settings: dict[str, Any]) -> str:
    ready = bool(doctor.get("ok"))
    song_count = len(songs)
    return f"""
<section class="hero">
  <div><h1>First Run Wizard</h1><div class="subtle">A guided local setup path for the first import, first separation, and first MKV.</div></div>
  <span class="badge {'ok' if ready else 'bad'}">{'ready' if ready else 'needs attention'}</span>
</section>
<section class="grid-2">
  <div class="panel tight">
    <h2>1. Check Runtime</h2>
    <div class="subtle">Doctor checks FFmpeg, yt-dlp, optional Demucs/FunASR, and library folders.</div>
    <a class="button secondary" href="/doctor">Open Doctor</a>
  </div>
  <div class="panel tight">
    <h2>2. Import Sample</h2>
    <div class="subtle">Uses assets/朋友-周华健.mkv and sample lyrics so you can test the workflow without typing a file path.</div>
    <form method="post" action="/sample/import"><button type="submit">Import Bundled Sample</button></form>
  </div>
  <div class="panel tight">
    <h2>3. Tune Defaults</h2>
    <div class="subtle">Current workers: {escape(str(settings.get("worker_count")))}; preview duration: {escape(str(settings.get("preview_duration")))}s.</div>
    <a class="button secondary" href="/settings">Open Settings</a>
  </div>
  <div class="panel tight">
    <h2>4. Continue Library</h2>
    <div class="subtle">{song_count} song(s) imported. Choose a song and run stages separately.</div>
    <a class="button secondary" href="/">Open Songs</a>
  </div>
</section>
"""

def render_import_confirm(source: str, song_id: str, title: str, artist: str) -> str:
    derived = normalize_song_id(song_id) if song_id else "derived from URL"
    return f"""
<section class="hero">
  <div><h1>Confirm URL Import</h1><div class="subtle">Remote downloads are queued only after rights confirmation.</div></div>
</section>
<section class="panel stack">
  <div><strong>URL</strong><div class="path">{escape(source)}</div></div>
  <div><strong>Song ID</strong><div class="compact">{escape(derived)}</div></div>
  <form method="post" action="/import" class="stack">
    <input type="hidden" name="source" value="{escape(source)}">
    <input type="hidden" name="song_id" value="{escape(song_id)}">
    <input type="hidden" name="title" value="{escape(title)}">
    <input type="hidden" name="artist" value="{escape(artist)}">
    <input type="hidden" name="confirm" value="1">
    <label class="checkbox-line"><input name="rights" value="1" type="checkbox" required> 我确认自己有权下载并处理这个 URL，仅用于个人本地制作。</label>
    <div class="row"><button type="submit">Queue Download</button><a class="button secondary" href="/">Cancel</a></div>
  </form>
</section>
"""

def render_storage(report: dict[str, Any]) -> str:
    root_rows = "".join(
        f"<tr><td>{escape(str(row.get('name') or ''))}</td><td class='path'>{escape(str(row.get('path') or ''))}</td><td>{escape(str(row.get('size') or ''))}</td></tr>"
        for row in report.get("roots") or []
    )
    song_rows = "".join(
        f"<tr><td><a href='{song_url(str(song.get('song_id') or ''))}'>{escape(str(song.get('song_id') or ''))}</a></td><td>{escape(str(song.get('total') or ''))}</td></tr>"
        for song in report.get("songs") or []
    )
    return f"""
<section class="hero">
  <div><h1>Disk Manager</h1><div class="subtle">Track raw, work, output, takes, jobs, and inbox storage.</div></div>
  <span class="badge">{escape(str(report.get("total") or "0 B"))}</span>
</section>
<section class="grid-2">
  <div class="panel"><h2>Library Roots</h2><table><thead><tr><th>Name</th><th>Path</th><th>Size</th></tr></thead><tbody>{root_rows}</tbody></table></div>
  <div class="panel"><h2>Largest Songs</h2><table><thead><tr><th>Song</th><th>Size</th></tr></thead><tbody>{song_rows or "<tr><td colspan='2'><div class='empty'>No songs yet.</div></td></tr>"}</tbody></table></div>
</section>
"""

def render_roadmap() -> str:
    return """
<section class="hero">
  <div><h1>Roadmap</h1><div class="subtle">Explicit v1/v2 boundaries and non-goals.</div></div>
</section>
<section class="grid-2">
  <div class="panel tight"><h2>v1 Scope</h2><div>Local import, track preview, manual lyrics, Demucs separation, ASS generation, MKV mux, support bundle, and recoverable jobs.</div></div>
  <div class="panel tight"><h2>v2 Candidates</h2><div>Automatic lyric search, high-quality forced alignment backends, packaged desktop app, richer waveform subtitle editor, and managed browser automation.</div></div>
  <div class="panel tight"><h2>Non-Goals</h2><div>No DRM bypass, no copyright evasion, no hosted cloud library, and no mandatory Node frontend.</div></div>
  <div class="panel tight"><h2>Compatibility Target</h2><div>MKV playback is optimized for VLC and IINA first; QuickTime is treated as limited.</div></div>
</section>
"""

def render_settings(settings: dict[str, Any]) -> str:
    return f"""
<section class="hero">
  <div><h1>Settings</h1><div class="subtle">Local defaults for this library.</div></div>
</section>
<section class="panel">
  <form method="post" action="/settings" class="stack">
    <div class="fields">
      <div><label>Worker count</label><input name="worker_count" type="number" min="1" value="{fmt_attr(settings.get("worker_count"))}"></div>
      <div><label>Auto refresh seconds</label><input name="auto_refresh_seconds" type="number" min="1" value="{fmt_attr(settings.get("auto_refresh_seconds"))}"></div>
      <div><label>Default preview start</label><input name="preview_start" type="number" min="0" step="1" value="{fmt_attr(settings.get("preview_start"))}"></div>
      <div><label>Default preview duration</label><input name="preview_duration" type="number" min="1" step="1" value="{fmt_attr(settings.get("preview_duration"))}"></div>
      <div><label>Preview segments</label><input name="preview_count" type="number" min="1" max="5" value="{fmt_attr(settings.get("preview_count"))}"></div>
      <div><label>Preview spacing</label><input name="preview_spacing" type="number" min="1" step="1" value="{fmt_attr(settings.get("preview_spacing"))}"></div>
      <div><label>Preview preset</label><select name="preview_preset">{render_select_options(["manual", "chorus"], str(settings.get("preview_preset") or "manual"))}</select></div>
      <div><label>Demucs model</label><input name="demucs_model" value="{escape(str(settings.get("demucs_model") or "htdemucs"))}"></div>
      <div><label>Demucs device</label><select name="demucs_device">{render_select_options(["auto", "mps", "cpu", "cuda"], str(settings.get("demucs_device") or "auto"))}</select></div>
      <div><label>Normalize target I</label><input name="normalize_target_i" type="number" step="0.5" value="{fmt_attr(settings.get("normalize_target_i"))}"></div>
      <div><label>Default audio order</label><select name="default_audio_order">{render_select_options(["instrumental-first", "original-first"], str(settings.get("default_audio_order") or "instrumental-first"))}</select></div>
      <div><label>Default duration limit</label><input name="default_duration_limit" type="number" min="0" step="1" value="{fmt_attr(settings.get("default_duration_limit"))}"></div>
      <div><label>Subtitle font size</label><input name="subtitle_font_size" type="number" min="20" max="96" value="{fmt_attr(settings.get("subtitle_font_size"))}"></div>
      <div><label>Subtitle margin V</label><input name="subtitle_margin_v" type="number" min="10" max="180" value="{fmt_attr(settings.get("subtitle_margin_v"))}"></div>
      <div><label>Subtitle primary colour</label><input name="subtitle_primary_colour" value="{escape(str(settings.get("subtitle_primary_colour") or "&H00FFFFFF"))}"></div>
      <div><label>Subtitle secondary colour</label><input name="subtitle_secondary_colour" value="{escape(str(settings.get("subtitle_secondary_colour") or "&H0000D7FF"))}"></div>
      <div><label>Instrumental track title</label><input name="instrumental_track_title" value="{escape(str(settings.get("instrumental_track_title") or "伴奏"))}"></div>
      <div><label>Original track title</label><input name="original_track_title" value="{escape(str(settings.get("original_track_title") or "原唱"))}"></div>
      <div class="field-wide"><label>Output template</label><input name="output_template" value="{escape(str(settings.get("output_template") or "{song_id}.ktv.mkv"))}"></div>
      <label class="checkbox-line"><input name="package_include_logs" value="1" type="checkbox" {"checked" if settings.get("package_include_logs") else ""}> Include logs in support packages by default</label>
    </div>
    <div><button type="submit">Save Settings</button></div>
  </form>
</section>
"""
