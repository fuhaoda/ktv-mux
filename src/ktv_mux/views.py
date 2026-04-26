from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .paths import normalize_song_id

_BASE_TEMPLATE = Path(__file__).with_name("templates") / "base.html"


def page(title: str, body: str, *, auto_refresh: bool = False) -> str:
    refresh = '<meta http-equiv="refresh" content="3">' if auto_refresh else ""
    template = _BASE_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("{{ refresh }}", refresh)
        .replace("{{ title }}", escape(title))
        .replace("{{ body }}", body)
    )


def render_index(songs: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"<tr><td><a class='song-link' href='{song_url(song['song_id'])}'>{escape(song['song_id'])}</a></td>"
        f"<td>{escape(str(song.get('title') or ''))}</td>"
        f"<td>{escape(str(song.get('artist') or ''))}</td>"
        f"<td>{render_flags(song)}</td></tr>"
        for song in songs
    )
    if not rows:
        rows = "<tr><td colspan='4'><div class='empty'>No songs imported yet.</div></td></tr>"
    return f"""
<section class="hero">
  <div>
    <h1>Songs</h1>
    <div class="subtle">Import videos, choose tracks, generate instrumentals, and build MKV outputs.</div>
  </div>
</section>
<section class="grid-2">
  <div class="panel">
    <h2>Choose File</h2>
    <form method="post" action="/import-upload" enctype="multipart/form-data" class="stack">
      <div class="field-wide"><label>Source file</label><input name="file" type="file" required></div>
      <div class="fields">
        <div><label>Song ID optional</label><input name="song_id" placeholder="defaults to filename"></div>
        <div><label>Artist optional</label><input name="artist"></div>
        <div class="field-wide"><label>Title optional</label><input name="title"></div>
      </div>
      <div><button type="submit">Upload Source</button></div>
    </form>
  </div>
  <div class="panel">
    <h2>Import Path Or URL</h2>
    <form method="post" action="/import" class="stack">
      <div><label>Local path or URL</label><input name="source" required placeholder="assets/朋友-周华健.mkv"></div>
      <div class="fields">
        <div><label>Song ID optional</label><input name="song_id" placeholder="defaults to filename or URL"></div>
        <div><label>Artist optional</label><input name="artist"></div>
        <div class="field-wide"><label>Title optional</label><input name="title"></div>
      </div>
      <div><button type="submit">Import</button></div>
    </form>
  </div>
</section>
<section class="panel" style="margin-top:16px;">
  <h2>Library</h2>
  <table>
    <thead><tr><th>ID</th><th>Title</th><th>Artist</th><th>Files</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>
<section class="panel" style="margin-top:16px;">
  <h2>Recent Jobs</h2>
  {render_jobs(jobs)}
</section>
"""


def render_detail(
    song_id: str,
    summary: dict[str, Any],
    status: dict[str, Any],
    report: dict[str, Any],
    lyrics: str,
    ass: str,
    alignment: dict[str, Any],
    logs: list[str],
    jobs: list[dict[str, Any]],
    doctor: dict[str, Any],
    takes: list[dict[str, Any]],
) -> str:
    state = status.get("state") or "idle"
    state_class = (
        "ok" if state == "completed" else "warn" if state in {"running", "queued", "canceling"} else "bad" if state == "failed" else ""
    )
    current_stage = status.get("current_stage") or "none"
    selected_index = int((report or {}).get("selected_audio_index") or 0)
    keep_audio_index = int((report or {}).get("kept_audio_index") or 0)
    audio_blocks = render_audio_blocks(song_id, summary)
    output_blocks = render_outputs(song_id, summary, report, takes)
    return f"""
<section class="hero">
  <div>
    <h1>{escape(song_id)}</h1>
    <div class="subtle">{escape(str(summary.get("source_path") or ""))}</div>
  </div>
  <div class="row">{render_flags(summary)} <span class="badge {state_class}">{escape(state)}</span> <span class="badge">{escape(current_stage)}</span></div>
</section>
<section class="grid-2">
  <div class="stack">
    <div class="panel">
      <h2>Workflow</h2>
      <div class="steps">
        <form class="step" method="post" action="{song_url(song_id)}/run/probe">
          <strong>Probe</strong>
          <button type="submit">Read Tracks</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/extract">
          <strong>Extract Audio</strong>
          <label>Source track</label>
          <select name="audio_index">{render_audio_options(report, selected_index)}</select>
          <button type="submit">Extract</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/preview-tracks">
          <strong>Preview Tracks</strong>
          <label>Start seconds</label>
          <input name="preview_start" type="number" step="1" min="0" value="0">
          <label>Duration</label>
          <input name="preview_duration" type="number" step="1" min="3" value="20">
          <button type="submit">Build Previews</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/separate">
          <strong>Separate</strong>
          <button type="submit">Make Stem</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/replace-audio">
          <strong>Replace Track 2</strong>
          <label>Keep original track</label>
          <select name="keep_audio_index">{render_audio_options(report, keep_audio_index)}</select>
          <button type="submit">Build MKV</button>
        </form>
      </div>
      <div class="row" style="margin-top:12px;">
        <form method="post" action="{song_url(song_id)}/run/process"><button class="secondary" type="submit">Run Full Process</button></form>
      </div>
    </div>
    <div class="panel">
      <h2>Source Tracks</h2>
      {render_track_panel(song_id, report)}
    </div>
    <div class="panel">
      <h2>Audio Preview</h2>
      {audio_blocks}
    </div>
    <div class="panel">
      <h2>Lyrics</h2>
      <form method="post" action="{song_url(song_id)}/lyrics" class="stack">
        <textarea name="lyrics">{escape(lyrics)}</textarea>
        <div class="row"><button type="submit">Save Lyrics</button></div>
      </form>
      <form method="post" action="{song_url(song_id)}/lyrics-file" enctype="multipart/form-data" class="row" style="margin-top:10px;">
        <input name="file" type="file" accept=".txt,text/plain" required>
        <button class="secondary" type="submit">Upload lyrics.txt</button>
      </form>
      <div class="row" style="margin-top:12px;">
        <form method="post" action="{song_url(song_id)}/run/align"><button class="secondary" type="submit">Generate ASS</button></form>
        <form method="post" action="{song_url(song_id)}/shift" class="row">
          <input class="number-input" name="seconds" type="number" step="0.05" value="0">
          <button class="secondary" type="submit">Shift ASS</button>
        </form>
        <form method="post" action="{song_url(song_id)}/run/mux">
          <input type="hidden" name="audio_order" value="instrumental-first">
          <button class="secondary" type="submit">Build KTV MKV</button>
        </form>
      </div>
      {render_alignment_editor(song_id, alignment)}
    </div>
  </div>
  <div class="stack">
    <div class="panel">
      <h2>Outputs</h2>
      {output_blocks}
    </div>
    <div class="panel">
      <h2>Quality</h2>
      {render_quality(report)}
    </div>
    <div class="panel">
      <h2>Status</h2>
      {render_status(status)}
    </div>
    <div class="panel">
      <h2>Diagnostics</h2>
      {render_doctor_summary(doctor)}
    </div>
    <div class="panel">
      <h2>Recent Jobs</h2>
      {render_jobs(jobs)}
    </div>
    <div class="panel">
      <h2>Logs</h2>
      {render_logs(song_id, logs)}
    </div>
    <div class="panel">
      <h2>Report</h2>
      <pre>{escape(json_dump(compact_report(report)))}</pre>
    </div>
    <div class="panel">
      <h2>ASS Preview</h2>
      <pre>{escape(ass[:6000] or "No ASS generated yet.")}</pre>
    </div>
    <div class="panel danger-zone">
      <h2>Library Management</h2>
      <div class="tight">
        <form method="post" action="{song_url(song_id)}/run/clean-work"><button class="secondary" type="submit">Clean Regenerable Work Files</button></form>
        <form method="post" action="{song_url(song_id)}/delete" class="tight">
          <label>Type this ID to delete: {escape(song_id)}</label>
          <input name="confirm" placeholder="{escape(song_id)}">
          <div><button class="danger" type="submit">Delete Song</button></div>
        </form>
      </div>
    </div>
  </div>
</section>
"""


def render_audio_blocks(song_id: str, summary: dict[str, Any]) -> str:
    blocks = []
    for key, title, kind in [
        ("has_mix", "Extracted Mix", "mix"),
        ("has_instrumental", "Instrumental", "instrumental"),
        ("has_vocals", "Vocals Stem", "vocals"),
    ]:
        if summary.get(key):
            blocks.append(
                f"<h3>{escape(title)}</h3><audio controls src='{song_url(song_id)}/audio/{kind}'></audio>"
                f"<div class='row'><a class='button secondary' href='{song_url(song_id)}/download/{kind}'>Download {escape(title)}</a></div>"
            )
    if not blocks:
        return "<div class='empty'>No audio preview yet.</div>"
    return "".join(blocks)


def render_track_panel(song_id: str, report: dict[str, Any]) -> str:
    audio_streams = [s for s in (((report or {}).get("probe") or {}).get("streams") or []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        return "<div class='empty'>Run Probe to inspect source audio tracks.</div>"
    rows = []
    previews = {int(item.get("audio_index", -1)): item for item in (report.get("track_previews") or [])}
    for audio_index, stream in enumerate(audio_streams):
        details = audio_details(stream)
        preview = previews.get(audio_index)
        player = (
            f"<audio controls src='{song_url(song_id)}/audio/track-preview-{audio_index + 1}'></audio>"
            if preview
            else "<span class='subtle'>No preview yet.</span>"
        )
        rows.append(
            "<div class='track-grid'>"
            f"<div><strong>Track {audio_index + 1}</strong></div>"
            f"<div class='compact'>{escape(details)}</div>"
            f"<div>{player}</div>"
            "</div>"
        )
    return "<div class='tight'>" + "".join(rows) + "</div>"


def render_alignment_editor(song_id: str, alignment: dict[str, Any]) -> str:
    lines = alignment.get("lines") or []
    if not lines:
        return ""
    rows = []
    for index, item in enumerate(lines[:24]):
        rows.append(
            "<div class='alignment-row'>"
            f"<div class='compact'>Line {index + 1}</div>"
            f"<input name='line_{index}_start' type='number' step='0.01' value='{fmt_attr(item.get('start'))}'>"
            f"<input name='line_{index}_end' type='number' step='0.01' value='{fmt_attr(item.get('end'))}'>"
            f"<input name='line_{index}_text' value='{escape(str(item.get('text') or ''))}'>"
            "</div>"
        )
    note = "<div class='subtle'>Showing first 24 lines.</div>" if len(lines) > 24 else ""
    return f"""
      <div class="tight" style="margin-top:14px;">
        <h3>Subtitle Timing</h3>
        <img class="waveform" src="{song_url(song_id)}/waveform.svg" alt="Audio waveform">
        <form method="post" action="{song_url(song_id)}/alignment" class="tight">
          <input type="hidden" name="line_count" value="{min(len(lines), 24)}">
          {''.join(rows)}
          {note}
          <div><button class="secondary" type="submit">Save Subtitle Edits</button></div>
        </form>
      </div>
"""


def render_outputs(
    song_id: str,
    summary: dict[str, Any],
    report: dict[str, Any],
    takes: list[dict[str, Any]],
) -> str:
    rows = []
    if summary.get("has_instrumental"):
        rows.append(output_row("Instrumental WAV", f"{song_url(song_id)}/download/instrumental", "instrumental.wav"))
    if summary.get("has_audio_replaced_mkv"):
        rows.append(output_row("Audio-Replaced MKV", f"{song_url(song_id)}/download/audio-replaced-mkv", "new instrumental as Track 2"))
    if summary.get("has_mkv"):
        rows.append(output_row("KTV MKV", f"{song_url(song_id)}/download/ktv-mkv", "dual audio + ASS"))
    for take in takes:
        rows.append(render_take_row(song_id, take))
    if not rows:
        return "<div class='empty'>No outputs yet.</div>"
    latest = []
    for key in ["instrumental_take", "audio_replaced_mkv_take", "final_mkv_take"]:
        if report.get(key):
            latest.append(f"<div class='path'>{escape(str(report[key]))}</div>")
    if latest:
        rows.append("<div><strong>Latest versioned copies</strong>" + "".join(latest) + "</div>")
    return "<div class='stack'>" + "".join(rows) + "</div>"


def output_row(label: str, href: str, detail: str) -> str:
    return f"<div><div><strong>{escape(label)}</strong></div><div class='subtle'>{escape(detail)}</div><a class='button secondary' href='{href}'>Download</a></div>"


def render_take_row(song_id: str, take: dict[str, Any]) -> str:
    filename = str(take.get("filename") or "")
    encoded = quote(filename, safe="")
    current = "<span class='badge ok'>current</span>" if take.get("is_current") else ""
    return f"""
<div class="take-row">
  <div class="row"><strong>Saved Take</strong>{current}<span class="badge">{escape(str(take.get("kind") or ""))}</span></div>
  <div class="path">{escape(filename)}</div>
  <form method="post" action="{song_url(song_id)}/take/{encoded}/update" class="tight">
    <div class="take-meta">
      <div><label>Label</label><input name="label" value="{escape(str(take.get("label") or ""))}"></div>
      <div><label>Note</label><input name="note" value="{escape(str(take.get("note") or ""))}"></div>
    </div>
    <div class="row">
      <button class="secondary" type="submit">Save Note</button>
      <a class="button secondary" href="{song_url(song_id)}/download/take/{encoded}">Download</a>
    </div>
  </form>
  <div class="row">
    <form class="mini-form" method="post" action="{song_url(song_id)}/take/{encoded}/set-current"><button class="secondary" type="submit">Set Current</button></form>
    <form class="mini-form" method="post" action="{song_url(song_id)}/take/{encoded}/delete"><button class="danger" type="submit">Delete</button></form>
  </div>
</div>
"""


def render_quality(report: dict[str, Any]) -> str:
    quality = (report or {}).get("quality")
    if not isinstance(quality, dict):
        return "<div class='empty'>No quality metrics yet.</div>"
    rows = [
        "<div class='metric'><div>Stem</div><div>Duration</div><div>RMS dBFS</div><div>Peak dBFS</div><div>Clip</div></div>"
    ]
    for key, label in [("mix", "Mix"), ("instrumental", "Instrumental"), ("vocals", "Vocals")]:
        metric = quality.get(key) or {}
        rows.append(
            "<div class='metric'>"
            f"<div>{escape(label)}</div>"
            f"<div>{fmt(metric.get('duration'))}</div>"
            f"<div>{fmt(metric.get('rms_dbfs'))}</div>"
            f"<div>{fmt(metric.get('peak_dbfs'))}</div>"
            f"<div>{fmt_percent(metric.get('clipped_ratio'))}</div>"
            "</div>"
        )
    rows.append(
        f"<div class='subtle'>Instrumental RMS delta: {fmt(quality.get('instrumental_rms_delta_db'))}; "
        f"vocals RMS delta: {fmt(quality.get('vocals_rms_delta_db'))}; "
        f"instrumental silence: {fmt_percent((quality.get('instrumental') or {}).get('silence_ratio'))}</div>"
    )
    recommendations = quality.get("recommendations") or []
    if recommendations:
        rows.append(
            "<div class='tight'>"
            + "".join(f"<div class='badge warn'>{escape(str(item))}</div>" for item in recommendations)
            + "</div>"
        )
    return "<div class='tight'>" + "".join(rows) + "</div>"


def render_status(status: dict[str, Any]) -> str:
    if not status:
        return "<div class='empty'>No job history yet.</div>"
    history = status.get("history") or []
    rows = []
    for item in history[-8:]:
        state = str(item.get("state") or "")
        state_class = (
            "ok" if state == "completed" else "warn" if state in {"running", "queued", "canceling"} else "bad" if state == "failed" else ""
        )
        rows.append(
            f"<tr><td>{escape(str(item.get('time') or ''))}</td><td>{escape(str(item.get('stage') or ''))}</td>"
            f"<td><span class='badge {state_class}'>{escape(state)}</span></td><td class='compact'>{escape(trim(str(item.get('message') or ''), 160))}</td></tr>"
        )
    return f"<table><thead><tr><th>Time</th><th>Stage</th><th>State</th><th>Message</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


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
        rows.append(
            f"<tr><td>{escape(str(job.get('created_at') or ''))}</td>"
            f"<td><a href='{song_url(str(job.get('song_id') or ''))}'>{escape(str(job.get('song_id') or ''))}</a></td>"
            f"<td>{escape(str(job.get('stage') or ''))}</td>"
            f"<td><span class='badge {state_class}'>{escape(state)}</span></td>"
            f"<td><div class='progress'><span style='width:{progress}%'></span></div><div class='compact'>{progress}%</div></td>"
            f"<td class='compact'>{escape(trim(str(job.get('message') or ''), 160))}</td>"
            f"<td>{actions}</td></tr>"
        )
    return f"<table><thead><tr><th>Created</th><th>Song</th><th>Stage</th><th>State</th><th>Progress</th><th>Message</th><th>Actions</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


def render_job_actions(job: dict[str, Any]) -> str:
    job_id = escape(str(job.get("job_id") or ""))
    state = str(job.get("state") or "")
    if state in {"queued", "running", "canceling"}:
        return f"<form class='mini-form' method='post' action='/jobs/{job_id}/cancel'><button class='secondary' type='submit'>Cancel</button></form>"
    if state in {"failed", "canceled"}:
        return f"<form class='mini-form' method='post' action='/jobs/{job_id}/retry'><button class='secondary' type='submit'>Retry</button></form>"
    return ""


def render_logs(song_id: str, logs: list[str]) -> str:
    if not logs:
        return "<div class='empty'>No stage logs yet.</div>"
    links = "".join(
        f"<a class='button secondary' href='{song_url(song_id)}/log/{escape(stage)}' target='_blank'>{escape(stage)}.log</a>"
        for stage in logs
    )
    return f"<div class='row'>{links}</div>"


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
            f"<td class='compact'>{escape(str(check.get('hint') or ''))}</td></tr>"
        )
    return f"""
<section class="hero">
  <div><h1>Doctor</h1><div class="subtle">Dependency and library checks for the local KTV workflow.</div></div>
  <span class="badge {'ok' if doctor.get('ok') else 'bad'}">{'ready' if doctor.get('ok') else 'attention needed'}</span>
</section>
<section class="panel">
  <table>
    <thead><tr><th>Check</th><th>State</th><th>Detail</th><th>Hint</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
<section class="panel" style="margin-top:16px;">
  <h2>Library</h2>
  <pre>{escape(json_dump(doctor.get('library') or {}))}</pre>
</section>
"""


def render_audio_options(report: dict[str, Any], selected_index: int) -> str:
    audio_streams = []
    for stream in ((report or {}).get("probe") or {}).get("streams") or []:
        if stream.get("codec_type") == "audio":
            audio_streams.append(stream)
    if not audio_streams:
        audio_streams = [{"index": 0}, {"index": 1}]

    options = []
    for audio_index, stream in enumerate(audio_streams):
        selected = " selected" if audio_index == selected_index else ""
        details = audio_details(stream)
        label = f"Track {audio_index + 1}"
        if details:
            label = f"{label} - {details}"
        options.append(f"<option value='{audio_index}'{selected}>{escape(label)}</option>")
    return "".join(options)


def audio_details(stream: dict[str, Any]) -> str:
    codec = stream.get("codec_name") or "audio"
    channels = stream.get("channels")
    sample_rate = stream.get("sample_rate")
    language = (stream.get("tags") or {}).get("language")
    title = (stream.get("tags") or {}).get("title")
    default = "default" if (stream.get("disposition") or {}).get("default") else ""
    values = [codec, sample_rate, f"{channels}ch" if channels else "", language, title, default]
    return " ".join(str(item) for item in values if item)


def render_flags(song: dict[str, Any]) -> str:
    labels = [
        ("has_source", "source"),
        ("has_lyrics", "lyrics"),
        ("has_mix", "mix"),
        ("has_instrumental", "instrumental"),
        ("has_ass", "ass"),
        ("has_audio_replaced_mkv", "audio-mkv"),
        ("has_mkv", "ktv-mkv"),
    ]
    return " ".join(f"<span class='flag'>{escape(label)}</span>" for key, label in labels if song.get(key))


def render_delete_confirm(song_id: str) -> str:
    return f"""
<section class="panel danger-zone stack">
  <h1>Confirm Delete</h1>
  <div class="subtle">Type the exact song ID before deleting.</div>
  <form method="post" action="{song_url(song_id)}/delete" class="stack">
    <label>Song ID</label>
    <input name="confirm" placeholder="{escape(song_id)}">
    <div class="row">
      <button class="danger" type="submit">Delete Song</button>
      <a class="button secondary" href="{song_url(song_id)}">Cancel</a>
    </div>
  </form>
</section>
"""


def render_error(message: str, trace: str) -> str:
    return f"""
<section class="hero"><div><h1>Something Needs Attention</h1><div class="subtle">The request did not complete.</div></div></section>
<section class="panel stack">
  <div class="badge bad">{escape(trim(message, 300))}</div>
  <pre>{escape(trace)}</pre>
  <div><a class="button secondary" href="/">Back to songs</a></div>
</section>
"""


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    if not report:
        return {}
    clone = dict(report)
    probe = clone.get("probe")
    if isinstance(probe, dict):
        clone["probe"] = {
            "duration": probe.get("duration"),
            "video_streams": probe.get("video_streams"),
            "audio_streams": probe.get("audio_streams"),
            "subtitle_streams": probe.get("subtitle_streams"),
        }
    if clone.get("failure"):
        clone["failure"] = trim(str(clone["failure"]), 1200)
    return clone


def song_url(song_id: str) -> str:
    return f"/songs/{quote(normalize_song_id(song_id), safe='')}"


def trim(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "..."


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return escape(str(value))


def fmt_attr(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return escape(str(value))


def fmt_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return escape(str(value))


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
