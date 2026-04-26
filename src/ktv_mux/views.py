from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .paths import normalize_song_id
from .separation_presets import PRESETS

_BASE_TEMPLATE = Path(__file__).with_name("templates") / "base.html"


def page(title: str, body: str, *, auto_refresh: bool = False, refresh_seconds: int = 3) -> str:
    refresh = f'<meta http-equiv="refresh" content="{int(refresh_seconds)}">' if auto_refresh else ""
    template = _BASE_TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("{{ refresh }}", refresh)
        .replace("{{ title }}", escape(title))
        .replace("{{ body }}", body)
    )


def render_index(
    songs: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    *,
    query: str = "",
    file_filter: str = "",
    inbox_files: list[str] | None = None,
    storage: dict[str, Any] | None = None,
) -> str:
    songs = sorted(songs, key=lambda song: str(song.get("updated_at") or song.get("created_at") or ""), reverse=True)
    rows = "\n".join(
        f"<tr><td><a class='song-link' href='{song_url(song['song_id'])}'>{escape(song['song_id'])}</a></td>"
        f"<td>{escape(str(song.get('title') or ''))}</td>"
        f"<td>{escape(str(song.get('artist') or ''))}</td>"
        f"<td>{render_flags(song)}</td>"
        f"<td class='compact'>{escape(str(song.get('updated_at') or ''))}</td></tr>"
        for song in songs
    )
    if not rows:
        rows = "<tr><td colspan='5'><div class='empty'>No songs imported yet.</div></td></tr>"
    return f"""
<section class="hero">
  <div>
    <h1>Songs</h1>
    <div class="subtle">Import videos, choose tracks, generate instrumentals, and build MKV outputs.</div>
  </div>
  <div class="row">
    <a class="button secondary" href="/wizard">First Run Wizard</a>
    <form method="post" action="/sample/import"><button class="secondary" type="submit">Import Bundled Sample</button></form>
  </div>
</section>
<section class="panel module-launcher">
  <h2>Single Module Launcher</h2>
  <div class="module-grid">
    <a class="module-card" href="#import">Import</a>
    <a class="module-card" href="#tracks">Track Review</a>
    <a class="module-card" href="#audio">Generate Instrumental</a>
    <a class="module-card" href="#lyrics">Subtitle Workbench</a>
    <a class="module-card" href="#mux">Replace / Mux</a>
    <a class="module-card" href="#jobs">Jobs</a>
  </div>
</section>
<section class="grid-2">
  <div class="panel" id="import">
    <h2>Choose File</h2>
    <form method="post" action="/import-upload" enctype="multipart/form-data" class="stack drop-zone">
      <div class="field-wide"><label>Source files</label><input name="files" type="file" multiple required></div>
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
      <label class="checkbox-line"><input name="rights" value="1" type="checkbox" required> 我确认自己有权处理这个本地文件或 URL，仅用于个人本地制作。</label>
      <div class="fields">
        <div><label>Song ID optional</label><input name="song_id" placeholder="defaults to filename or URL"></div>
        <div><label>Artist optional</label><input name="artist"></div>
        <div class="field-wide"><label>Title optional</label><input name="title"></div>
      </div>
      <div><button type="submit">Import</button></div>
    </form>
  </div>
</section>
<section class="grid-2" style="margin-top:16px;">
  <div class="panel">
    <h2>Search & Filter</h2>
    <form method="get" action="/" class="row">
      <input name="q" value="{escape(query)}" placeholder="song id, title, or artist">
      <select name="file_filter">{render_select_options(["", "source", "lyrics", "instrumental", "ktv-mkv"], file_filter)}</select>
      <button class="secondary" type="submit">Filter</button>
      <a class="button secondary" href="/">Reset</a>
    </form>
  </div>
  <div class="panel">
    <h2>Batch Console</h2>
    <form method="post" action="/batch-stage" class="row">
      <select name="stage">{render_select_options(["probe", "preview-tracks", "extract", "separate", "separate-sample"], "probe")}</select>
      <input class="number-input" name="audio_index" type="number" min="0" value="0" title="zero-based audio index">
      <select name="separation_preset">{render_select_options(sorted(PRESETS), "balanced")}</select>
      <input class="number-input" name="limit" type="number" min="1" placeholder="limit">
      <label class="checkbox-line"><input name="skip_completed" value="1" type="checkbox"> Skip completed</label>
      <label class="checkbox-line"><input name="dry_run" value="1" type="checkbox"> Dry run</label>
      <label class="checkbox-line"><input name="stop_on_error" value="1" type="checkbox"> Stop after first submit</label>
      <button class="secondary" type="submit">Queue Batch</button>
    </form>
  </div>
</section>
<section class="grid-2" style="margin-top:16px;">
  <div class="panel">
    <h2>Inbox Auto-Import</h2>
    <div class="subtle">Drop media files into library/inbox, then scan to import them with filename-based song IDs.</div>
    <div class="compact">{escape(', '.join(inbox_files or []) or 'No inbox files waiting.')}</div>
    <form method="post" action="/inbox-scan" class="row" style="margin-top:10px;"><button class="secondary" type="submit">Scan Inbox</button></form>
  </div>
  <div class="panel">
    <h2>Storage</h2>
    <div class="subtle">Library size: {escape(str((storage or {}).get("total") or "0 B"))}</div>
    <a class="button secondary" href="/storage">Open Disk Manager</a>
  </div>
</section>
<section class="panel" style="margin-top:16px;">
  <h2>Library</h2>
  <table>
    <thead><tr><th>ID</th><th>Title</th><th>Artist</th><th>Files</th><th>Updated</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>
{render_recent_imports(songs)}
<section class="panel" style="margin-top:16px;">
  <h2>Recent Jobs</h2>
  <form method="post" action="/jobs/prune" style="margin-bottom:10px;"><button class="secondary" type="submit">Prune Finished Jobs</button></form>
  {render_jobs(jobs)}
</section>
"""


def render_recent_imports(songs: list[dict[str, Any]]) -> str:
    recent = [song for song in songs if song.get("source_path")][:5]
    if not recent:
        return ""
    rows = "".join(
        f"<tr><td><a href='{song_url(str(song.get('song_id') or ''))}'>{escape(str(song.get('song_id') or ''))}</a></td>"
        f"<td>{escape(str(song.get('title') or ''))}</td>"
        f"<td class='path'>{escape(str(song.get('source_path') or ''))}</td>"
        f"<td class='compact'>{escape(str(song.get('updated_at') or ''))}</td></tr>"
        for song in recent
    )
    return f"""
<section class="panel" style="margin-top:16px;">
  <h2>Recent Imports</h2>
  <table><thead><tr><th>ID</th><th>Title</th><th>Source</th><th>Updated</th></tr></thead><tbody>{rows}</tbody></table>
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
    actions: list[dict[str, Any]],
    settings: dict[str, Any],
    log_tails: dict[str, str],
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
    preview_start = fmt_attr(settings.get("preview_start"))
    preview_duration = fmt_attr(settings.get("preview_duration"))
    preview_count = int(settings.get("preview_count") or 1)
    preview_spacing = fmt_attr(settings.get("preview_spacing"))
    preview_preset = str(settings.get("preview_preset") or "manual")
    demucs_model = str(settings.get("demucs_model") or "htdemucs")
    demucs_device = str(settings.get("demucs_device") or "auto")
    normalize_target_i = fmt_attr(settings.get("normalize_target_i"))
    default_audio_order = str(settings.get("default_audio_order") or "instrumental-first")
    default_duration_limit = fmt_attr(settings.get("default_duration_limit"))
    return f"""
<section class="hero">
  <div>
    <h1>{escape(song_id)}</h1>
    <div class="subtle">{escape(str(summary.get("source_path") or ""))}</div>
  </div>
  <div class="row">{render_flags(summary)} <span class="badge {state_class}">{escape(state)}</span> <span class="badge">{escape(current_stage)}</span></div>
</section>
{render_duplicate_warning(report)}
{render_failure_recovery(song_id, report)}
<nav class="workflow-tabs">
  <a href="#tracks">Tracks</a>
  <a href="#audio">Audio</a>
  <a href="#lyrics">Lyrics</a>
  <a href="#mux">Mux</a>
  <a href="#outputs">Outputs</a>
  <a href="#jobs">Jobs</a>
</nav>
<section class="grid-2">
  <div class="stack">
    <div class="panel" id="audio">
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
          <input name="preview_start" type="number" step="1" min="0" value="{preview_start}">
          <label>Duration</label>
          <input name="preview_duration" type="number" step="1" min="3" value="{preview_duration}">
          <label>Segments</label>
          <input name="preview_count" type="number" step="1" min="1" max="5" value="{preview_count}">
          <label>Preset</label>
          <select name="preview_preset">{render_select_options(["manual", "chorus"], preview_preset)}</select>
          <input type="hidden" name="preview_spacing" value="{preview_spacing}">
          <button type="submit">Build Previews</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/separate">
          <strong>Separate</strong>
          <label>Preset</label>
          <select name="separation_preset">{render_select_options(sorted(PRESETS), "balanced")}</select>
          <label>Model</label>
          <input name="model" placeholder="{escape(demucs_model)}">
          <label>Device</label>
          <select name="device">{render_select_options(["auto", "mps", "cpu", "cuda"], demucs_device)}</select>
          <button type="submit">Make Stem</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/separate-sample">
          <strong>Sample Separate</strong>
          <label>Source track</label>
          <select name="audio_index">{render_audio_options(report, selected_index)}</select>
          <label>Start / Duration</label>
          <input name="preview_start" type="number" step="1" min="0" value="{preview_start}">
          <input name="preview_duration" type="number" step="1" min="3" value="30">
          <label>Preset</label>
          <select name="separation_preset">{render_select_options(sorted(PRESETS), "fast-review")}</select>
          <button type="submit">Try Segment</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/replace-audio">
          <strong>Replace Track 2</strong>
          <label>Keep original track</label>
          <select name="keep_audio_index">{render_audio_options(report, keep_audio_index)}</select>
          <label class="checkbox-line"><input name="copy_subtitles" value="1" type="checkbox" checked> Copy source subtitles</label>
          <label>Limit seconds optional</label>
          <input name="duration_limit" type="number" step="1" min="1">
          <button type="submit">Build MKV</button>
        </form>
        <form class="step" method="post" action="{song_url(song_id)}/run/remake-track">
          <strong>Remake Track</strong>
          <label>Separate track</label>
          <select name="audio_index">{render_audio_options(report, selected_index)}</select>
          <label>Keep original track</label>
          <select name="keep_audio_index">{render_audio_options(report, keep_audio_index)}</select>
          <label>Preset</label>
          <select name="separation_preset">{render_select_options(sorted(PRESETS), "balanced")}</select>
          <label class="checkbox-line"><input name="copy_subtitles" value="1" type="checkbox" checked> Copy subtitles</label>
          <button type="submit">Remake + Replace</button>
        </form>
      </div>
      <div class="row" style="margin-top:12px;">
        <form method="post" action="{song_url(song_id)}/run/process"><input type="hidden" name="align_backend" value="auto"><button class="secondary" type="submit">Run Full Process</button></form>
        <form method="post" action="{song_url(song_id)}/run/process-from" class="row">
          <select name="start_stage">{render_select_options(["probe", "extract", "separate", "align", "mux"], "separate")}</select>
          <input type="hidden" name="align_backend" value="auto">
          <button class="secondary" type="submit">Run From Stage</button>
        </form>
        <form method="post" action="{song_url(song_id)}/run/normalize" class="row">
          <input class="number-input" name="target_i" type="number" step="0.5" value="{normalize_target_i}">
          <label><input name="replace_current" type="checkbox" value="1" style="width:auto;"> Replace</label>
          <button class="secondary" type="submit">Normalize</button>
        </form>
      </div>
    </div>
    <div class="panel" id="tracks">
      <h2>Source Tracks</h2>
      {render_track_panel(song_id, report)}
    </div>
    <div class="panel">
      <h2>Audio Preview</h2>
      {audio_blocks}
    </div>
    <div class="panel">
      <h2>A/B Review</h2>
      {render_ab_review(song_id, summary, takes)}
    </div>
    <div class="panel" id="lyrics">
      <h2>Subtitle Workbench</h2>
      <form method="post" action="{song_url(song_id)}/lyrics" class="stack">
        <textarea name="lyrics" data-draft-key="{escape(song_id)}:lyrics">{escape(lyrics)}</textarea>
        <div class="row"><button type="submit">Save Lyrics</button></div>
      </form>
      <form method="post" action="{song_url(song_id)}/lyrics-file" enctype="multipart/form-data" class="row" style="margin-top:10px;">
        <input name="file" type="file" accept=".txt,.lrc,.srt,.ass,text/plain" required>
        <button class="secondary" type="submit">Upload lyrics file</button>
      </form>
      <div class="row" style="margin-top:10px;">
        <form method="post" action="{song_url(song_id)}/run/extract-subtitles" class="row">
          <input class="number-input" name="subtitle_index" type="number" min="0" value="0">
          <button class="secondary" type="submit">Extract Embedded Subtitles</button>
        </form>
        <form method="post" action="{song_url(song_id)}/instrumental-file" enctype="multipart/form-data" class="row">
          <input name="file" type="file" accept="audio/*,.wav,.aiff,.flac,.mp3" required>
          <input name="label" placeholder="candidate label">
          <button class="secondary" type="submit">Use External Instrumental</button>
        </form>
      </div>
      {render_lyrics_versions(summary)}
      <div class="row" style="margin-top:12px;">
        <form method="post" action="{song_url(song_id)}/run/align" class="row">
          <select name="align_backend">{render_select_options(["auto", "lrc", "funasr", "simple"], "auto")}</select>
          <button class="secondary" type="submit">Generate ASS</button>
        </form>
        <form method="post" action="{song_url(song_id)}/shift" class="row">
          <input class="number-input" name="seconds" type="number" step="0.05" value="0">
          <button class="secondary" type="submit">Shift ASS</button>
        </form>
        <form method="post" action="{song_url(song_id)}/run/mux" id="mux">
          <select name="audio_order">{render_select_options(["instrumental-first", "original-first"], default_audio_order)}</select>
          <input class="number-input" name="duration_limit" type="number" step="1" min="0" value="{default_duration_limit}" placeholder="seconds">
          <button class="secondary" type="submit">Build KTV MKV</button>
        </form>
      </div>
      {render_alignment_editor(song_id, alignment)}
    </div>
  </div>
  <div class="stack">
    <div class="panel">
      <h2>Next Actions</h2>
      {render_next_actions(song_id, actions)}
    </div>
    <div class="panel">
      <h2>Metadata</h2>
      {render_metadata_form(song_id, summary)}
    </div>
    <div class="panel" id="outputs">
      <h2>Outputs</h2>
      {output_blocks}
    </div>
    <div class="panel">
      <h2>Quality</h2>
      {render_quality(report)}
    </div>
    <div class="panel">
      <h2>Player Compatibility</h2>
      {render_compatibility(report)}
    </div>
    <div class="panel">
      <h2>Status</h2>
      {render_status(status)}
    </div>
    <div class="panel">
      <h2>Diagnostics</h2>
      {render_doctor_summary(doctor)}
    </div>
    <div class="panel" id="jobs">
      <h2>Recent Jobs</h2>
      {render_jobs(jobs)}
    </div>
    <div class="panel">
      <h2>Logs</h2>
      {render_logs(song_id, logs, log_tails)}
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
        ("has_instrumental_sample", "Sample Instrumental", "instrumental-sample"),
        ("has_normalized_instrumental", "Normalized Instrumental", "instrumental-normalized"),
        ("has_vocals", "Vocals Stem", "vocals"),
        ("has_vocals_sample", "Sample Vocals", "vocals-sample"),
    ]:
        if summary.get(key):
            blocks.append(
                f"<h3>{escape(title)}</h3><audio controls src='{song_url(song_id)}/audio/{kind}'></audio>"
                f"<div class='row'><a class='button secondary' href='{song_url(song_id)}/download/{kind}'>Download {escape(title)}</a></div>"
            )
    if not blocks:
        return "<div class='empty'>No audio preview yet.</div>"
    return "".join(blocks)


def render_duplicate_warning(report: dict[str, Any]) -> str:
    duplicates = report.get("duplicate_sources") or []
    hints = report.get("duplicate_source_hints") or []
    if not duplicates and not hints:
        return ""
    rows = "".join(
        f"<div><a href='{song_url(str(item.get('song_id') or ''))}'>{escape(str(item.get('song_id') or ''))}</a>"
        f"<div class='path'>{escape(str(item.get('path') or ''))}</div></div>"
        for item in duplicates
        if isinstance(item, dict)
    )
    hint_rows = "".join(
        f"<div><a href='{song_url(str(item.get('song_id') or ''))}'>{escape(str(item.get('song_id') or ''))}</a>"
        f"<span class='badge warn'>{escape(str(item.get('reason') or 'similar file'))}</span>"
        f"<div class='path'>{escape(str(item.get('path') or ''))}</div></div>"
        for item in hints
        if isinstance(item, dict)
    )
    return f"<section class='panel warning-panel' style='margin-bottom:16px;'><h2>Possible Duplicate Source</h2><div class='tight'>{rows}{hint_rows}</div></section>"


def render_failure_recovery(song_id: str, report: dict[str, Any]) -> str:
    failed_stage = str((report or {}).get("failed_stage") or "")
    failure = str((report or {}).get("failure") or "")
    if not failed_stage and not failure:
        return ""
    start_stage = failed_stage if failed_stage in {"probe", "extract", "separate", "align", "mux"} else "probe"
    rerun_button = ""
    if failed_stage in {"probe", "preview-tracks", "extract", "separate", "separate-sample", "align", "mux", "replace-audio", "normalize"}:
        rerun_button = (
            f"<form method='post' action='{song_url(song_id)}/run/{escape(failed_stage)}'>"
            "<input type='hidden' name='force' value='1'>"
            "<button class='secondary' type='submit'>Force Rerun Failed Stage</button></form>"
        )
    return f"""
<section class="panel warning-panel" style="margin-bottom:16px;">
  <h2>Failure Recovery</h2>
  <div class="badge bad">{escape(failed_stage or 'failed')}</div>
  <div class="compact">{escape(trim(failure, 500))}</div>
  <div class="row" style="margin-top:10px;">
    {rerun_button}
    <form method="post" action="{song_url(song_id)}/run/separate">
      <input type="hidden" name="device" value="cpu">
      <button class="secondary" type="submit">Retry Separate On CPU</button>
    </form>
    <form method="post" action="{song_url(song_id)}/run/separate-sample">
      <button class="secondary" type="submit">Test Short Segment</button>
    </form>
    <form method="post" action="{song_url(song_id)}/run/process-from">
      <input type="hidden" name="start_stage" value="{escape(start_stage)}">
      <button class="secondary" type="submit">Run From Failed Stage</button>
    </form>
  </div>
</section>
"""


def render_ab_review(song_id: str, summary: dict[str, Any], takes: list[dict[str, Any]]) -> str:
    rows = []
    if summary.get("has_mix"):
        rows.append(f"<div><strong>A Original Mix</strong><audio controls src='{song_url(song_id)}/audio/mix'></audio></div>")
    if summary.get("has_instrumental"):
        rows.append(f"<div><strong>B Current Instrumental</strong><audio controls src='{song_url(song_id)}/audio/instrumental'></audio></div>")
    instrumental_takes = [take for take in takes if take.get("kind") == "instrumental"][:4]
    for take in instrumental_takes:
        filename = str(take.get("filename") or "")
        encoded = quote(filename, safe="")
        score_value = "" if take.get("score") is None else str(take.get("score"))
        rows.append(
            f"<div class='take-row'><div class='row'><strong>Saved Instrumental Take</strong><span class='badge'>{escape(score_value or 'unscored')}</span></div>"
            f"<audio controls src='{song_url(song_id)}/download/take/{encoded}'></audio>"
            f"<form method='post' action='{song_url(song_id)}/take/{encoded}/update' class='row'>"
            f"<input name='label' value='{escape(str(take.get('label') or ''))}' placeholder='label'>"
            f"<input name='note' value='{escape(str(take.get('note') or ''))}' placeholder='listening note'>"
            f"<input class='number-input' name='score' type='number' min='1' max='5' value='{escape(score_value)}' placeholder='1-5'>"
            "<button class='secondary' type='submit'>Save Review</button></form></div>"
        )
    if not rows:
        return "<div class='empty'>Generate mix and instrumental audio to compare takes.</div>"
    return "<div class='tight'>" + "".join(rows) + "</div>"


def render_next_actions(song_id: str, actions: list[dict[str, Any]]) -> str:
    rows = []
    runnable = {"probe", "preview-tracks", "extract", "separate", "align", "replace-audio", "mux"}
    for action in actions:
        stage = str(action.get("stage") or "")
        label = escape(str(action.get("label") or stage))
        reason = escape(str(action.get("reason") or ""))
        button = ""
        if stage in runnable:
            button = (
                f"<form method='post' action='{song_url(song_id)}/run/{escape(stage)}'>"
                f"<button class='secondary' type='submit'>{label}</button></form>"
            )
        rows.append(f"<div class='tight'><div><strong>{label}</strong></div><div class='subtle'>{reason}</div>{button}</div>")
    return "<div class='tight'>" + "".join(rows) + "</div>"


def render_metadata_form(song_id: str, summary: dict[str, Any]) -> str:
    tags = ", ".join(str(tag) for tag in summary.get("tags") or [])
    rating = "" if summary.get("rating") is None else str(summary.get("rating"))
    return f"""
<form method="post" action="{song_url(song_id)}/metadata" class="tight">
  <div><label>Title</label><input name="title" value="{escape(str(summary.get("title") or ""))}"></div>
  <div><label>Artist</label><input name="artist" value="{escape(str(summary.get("artist") or ""))}"></div>
  <div><label>Tags</label><input name="tags" value="{escape(tags)}" placeholder="duet, needs-review"></div>
  <div><label>Rating</label><input name="rating" type="number" min="1" max="5" value="{escape(rating)}"></div>
  <div><button class="secondary" type="submit">Save Metadata</button></div>
</form>
<form method="post" action="{song_url(song_id)}/rename" class="tight" style="margin-top:10px;">
  <div><label>Song ID</label><input name="new_song_id" value="{escape(song_id)}"></div>
  <div><button class="secondary" type="submit">Rename Song</button></div>
</form>
"""


def render_track_panel(song_id: str, report: dict[str, Any]) -> str:
    audio_streams = [s for s in (((report or {}).get("probe") or {}).get("streams") or []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        return "<div class='empty'>Run Probe to inspect source audio tracks.</div>"
    rows = []
    previews: dict[int, list[dict[str, Any]]] = {}
    for item in report.get("track_previews") or []:
        previews.setdefault(int(item.get("audio_index", -1)), []).append(item)
    for audio_index, stream in enumerate(audio_streams):
        details = audio_details(stream)
        track_previews = sorted(previews.get(audio_index) or [], key=lambda item: int(item.get("segment") or 1))
        player = "".join(
            f"<div class='compact'>Segment {int(preview.get('segment') or 1)} @ {fmt(preview.get('start'))}s</div>"
            f"<audio controls src='{song_url(song_id)}/audio/track-preview-{audio_index + 1}-{int(preview.get('segment') or 1)}'></audio>"
            for preview in track_previews
        )
        if not player:
            player = "<span class='subtle'>No preview yet.</span>"
        rows.append(
            "<div class='track-grid'>"
            f"<div><strong>Track {audio_index + 1}</strong></div>"
            f"<div class='compact'>{escape(details)}</div>"
            f"<div>{player}<div class='row track-actions'>"
            f"<form method='post' action='{song_url(song_id)}/run/extract'><input type='hidden' name='audio_index' value='{audio_index}'><button class='secondary' type='submit'>Use Track {audio_index + 1} For Extract</button></form>"
            f"<form method='post' action='{song_url(song_id)}/run/separate-sample'><input type='hidden' name='audio_index' value='{audio_index}'><button class='secondary' type='submit'>Try Track {audio_index + 1}</button></form>"
            f"<form method='post' action='{song_url(song_id)}/run/remake-track'><input type='hidden' name='audio_index' value='{audio_index}'><input type='hidden' name='keep_audio_index' value='0'><input type='hidden' name='copy_subtitles' value='1'><button class='secondary' type='submit'>Remake From Track {audio_index + 1}</button></form>"
            "</div></div>"
            "</div>"
        )
    subtitle_panel = render_subtitle_tracks(song_id, report)
    return "<div class='tight'>" + "".join(rows) + subtitle_panel + "</div>"


def render_subtitle_tracks(song_id: str, report: dict[str, Any]) -> str:
    subtitle_streams = [
        s for s in (((report or {}).get("probe") or {}).get("streams") or []) if s.get("codec_type") == "subtitle"
    ]
    if not subtitle_streams:
        return ""
    rows = []
    for subtitle_index, stream in enumerate(subtitle_streams):
        details = audio_details(stream)
        rows.append(
            "<div class='track-grid'>"
            f"<div><strong>Subtitle {subtitle_index + 1}</strong></div>"
            f"<div class='compact'>{escape(details)}</div>"
            f"<form method='post' action='{song_url(song_id)}/run/extract-subtitles'>"
            f"<input type='hidden' name='subtitle_index' value='{subtitle_index}'>"
            f"<button class='secondary' type='submit'>Use As Lyrics</button></form>"
            "</div>"
        )
    return "<h3>Embedded Subtitles</h3>" + "".join(rows)


def render_alignment_editor(song_id: str, alignment: dict[str, Any]) -> str:
    lines = alignment.get("lines") or []
    if not lines:
        return ""
    line_ends = [float(line.get("end") or 0.0) for line in lines if isinstance(line, dict)]
    max_time = max(line_ends) if line_ends else 0.0
    rows = []
    for index, item in enumerate(lines[:24]):
        start_id = f"line-{index}-start"
        end_id = f"line-{index}-end"
        rows.append(
            "<div class='alignment-row'>"
            f"<div class='compact'>Line {index + 1}</div>"
            f"<div><input id='{start_id}' name='line_{index}_start' type='number' step='0.01' value='{fmt_attr(item.get('start'))}'>"
            f"<input type='range' min='0' max='600' step='0.01' value='{fmt_attr(item.get('start'))}' data-sync-target='#{start_id}'></div>"
            f"<div><input id='{end_id}' name='line_{index}_end' type='number' step='0.01' value='{fmt_attr(item.get('end'))}'>"
            f"<input type='range' min='0' max='600' step='0.01' value='{fmt_attr(item.get('end'))}' data-sync-target='#{end_id}'></div>"
            f"<input name='line_{index}_text' value='{escape(str(item.get('text') or ''))}'>"
            f"<button class='secondary icon-button' type='button' data-seek-time='{fmt_attr(item.get('start'))}'>Play</button>"
            "</div>"
        )
    note = "<div class='subtle'>Showing first 24 lines.</div>" if len(lines) > 24 else ""
    return f"""
      <div class="tight" style="margin-top:14px;">
        <h3>Subtitle Timing</h3>
        <audio class="subtitle-player" data-subtitle-player controls src="{song_url(song_id)}/audio/instrumental"></audio>
        <div class="row"><button class="secondary" type="button" data-use-playhead>Use Playhead For Focused Time</button><span class="subtle">Click a time input, play audio, then copy the current playhead.</span></div>
        <img class="waveform" data-duration="{fmt_attr(max_time)}" src="{song_url(song_id)}/waveform.svg" alt="Audio waveform">
        <form method="post" action="{song_url(song_id)}/alignment" class="tight">
          <input type="hidden" name="line_count" value="{min(len(lines), 24)}">
          {''.join(rows)}
          {note}
          <div><button class="secondary" type="submit">Save Subtitle Edits</button></div>
        </form>
        <form method="post" action="{song_url(song_id)}/alignment-shift-lines" class="row">
          <input class="number-input" name="start_line" type="number" min="1" value="1">
          <input class="number-input" name="end_line" type="number" min="1" value="{min(len(lines), 24)}">
          <input class="number-input" name="seconds" type="number" step="0.05" value="0">
          <button class="secondary" type="submit">Shift Lines</button>
        </form>
        <form method="post" action="{song_url(song_id)}/alignment-stretch-lines" class="row">
          <input class="number-input" name="start_line" type="number" min="1" value="1">
          <input class="number-input" name="end_line" type="number" min="1" value="{min(len(lines), 24)}">
          <input class="number-input" name="target_start" type="number" step="0.05" value="{fmt_attr((lines[0] or {}).get('start'))}">
          <input class="number-input" name="target_end" type="number" step="0.05" value="{fmt_attr((lines[min(len(lines), 24) - 1] or {}).get('end'))}">
          <button class="secondary" type="submit">Stretch Lines</button>
        </form>
      </div>
"""


def render_lyrics_versions(summary: dict[str, Any]) -> str:
    versions = summary.get("lyrics_versions") or []
    if not versions:
        return "<div class='subtle' style='margin-top:8px;'>No saved lyrics revisions yet.</div>"
    rows = "".join(f"<span class='badge'>{escape(str(name))}</span>" for name in versions[-6:])
    return f"<div class='tight' style='margin-top:8px;'><strong>Lyrics revisions</strong><div class='row'>{rows}</div></div>"


def render_outputs(
    song_id: str,
    summary: dict[str, Any],
    report: dict[str, Any],
    takes: list[dict[str, Any]],
) -> str:
    rows = []
    if summary.get("has_instrumental"):
        rows.append(output_row("Instrumental WAV", f"{song_url(song_id)}/download/instrumental", "instrumental.wav", song_id=song_id, kind="instrumental"))
    if summary.get("has_instrumental_sample"):
        rows.append(
            output_row(
                "Sample Instrumental WAV",
                f"{song_url(song_id)}/download/instrumental-sample",
                "instrumental.sample.wav",
                song_id=song_id,
                kind="instrumental-sample",
            )
        )
    if summary.get("has_normalized_instrumental"):
        rows.append(
            output_row(
                "Normalized Instrumental WAV",
                f"{song_url(song_id)}/download/instrumental-normalized",
                "instrumental.normalized.wav",
                song_id=song_id,
                kind="instrumental-normalized",
            )
        )
    if summary.get("has_audio_replaced_mkv"):
        rows.append(output_row("Audio-Replaced MKV", f"{song_url(song_id)}/download/audio-replaced-mkv", "new instrumental as Track 2", song_id=song_id, kind="audio-replaced-mkv", video=True))
    if summary.get("has_mkv"):
        rows.append(output_row("KTV MKV", f"{song_url(song_id)}/download/ktv-mkv", "dual audio + ASS", song_id=song_id, kind="ktv-mkv", video=True))
    templated = report.get("templated_final_mkv")
    if templated:
        rows.append(output_row("Template-Named MKV", f"{song_url(song_id)}/download/templated-final-mkv", Path(str(templated)).name))
    if rows:
        rows.append(output_row("Package ZIP", f"{song_url(song_id)}/export", "outputs, reports, lyrics, and takes"))
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
    audit_blocks = []
    for key, label in [("final_mkv_audit", "KTV MKV Audit"), ("audio_replaced_mkv_audit", "Audio-Replaced MKV Audit")]:
        if isinstance(report.get(key), dict):
            audit_blocks.append(render_mkv_audit(label, report[key]))
    rows.extend(audit_blocks)
    return "<div class='stack'>" + "".join(rows) + "</div>"


def output_row(label: str, href: str, detail: str, *, song_id: str = "", kind: str = "", video: bool = False) -> str:
    reveal = (
        f"<a class='button secondary' href='{song_url(song_id)}/reveal/{escape(kind)}'>Reveal</a>"
        if song_id and kind
        else ""
    )
    preview = f"<video controls src='{href}'></video>" if video else ""
    return (
        f"<div><div><strong>{escape(label)}</strong></div><div class='subtle'>{escape(detail)}</div>"
        f"{preview}<div class='row'><a class='button secondary' href='{href}'>Download</a>{reveal}</div></div>"
    )


def render_mkv_audit(label: str, audit: dict[str, Any]) -> str:
    state = "ok" if audit.get("ok") else "warn"
    warnings = audit.get("warnings") or []
    warning_html = "".join(f"<div class='badge warn'>{escape(str(item))}</div>" for item in warnings)
    return (
        f"<div class='tight'><div class='row'><strong>{escape(label)}</strong>"
        f"<span class='badge {state}'>{'ok' if audit.get('ok') else 'check'}</span></div>"
        f"<div class='compact'>video {fmt(audit.get('video_streams'))}; audio {fmt(audit.get('audio_streams'))}; "
        f"subtitle {fmt(audit.get('subtitle_streams'))}; default audio {escape(str(audit.get('default_audio_indexes') or []))}</div>"
        f"{warning_html}</div>"
    )


def render_take_row(song_id: str, take: dict[str, Any]) -> str:
    filename = str(take.get("filename") or "")
    encoded = quote(filename, safe="")
    current = "<span class='badge ok'>current</span>" if take.get("is_current") else ""
    score_value = "" if take.get("score") is None else str(take.get("score"))
    return f"""
<div class="take-row">
  <div class="row"><strong>Saved Take</strong>{current}<span class="badge">{escape(str(take.get("kind") or ""))}</span><span class="badge">{escape(score_value or "unscored")}</span></div>
  <div class="path">{escape(filename)}</div>
  <form method="post" action="{song_url(song_id)}/take/{encoded}/update" class="tight">
    <div class="take-meta">
      <div><label>Label</label><input name="label" value="{escape(str(take.get("label") or ""))}"></div>
      <div><label>Note</label><input name="note" value="{escape(str(take.get("note") or ""))}"></div>
      <div><label>Score</label><input name="score" type="number" min="1" max="5" value="{escape(score_value)}"></div>
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
        f"residual vocal risk: {escape(str(quality.get('vocal_bleed_risk') or 'unknown'))}; "
        f"instrumental silence: {fmt_percent((quality.get('instrumental') or {}).get('silence_ratio'))}; "
        f"duration delta: {fmt(quality.get('duration_delta_seconds'))}s</div>"
    )
    recommendations = quality.get("recommendations") or []
    recommendations_zh = quality.get("recommendations_zh") or []
    if recommendations_zh:
        rows.append(
            "<div class='tight'>"
            + "".join(f"<div class='badge warn'>{escape(str(item))}</div>" for item in recommendations_zh)
            + "</div>"
        )
    if recommendations:
        rows.append(
            "<div class='tight'>"
            + "".join(f"<div class='badge warn'>{escape(str(item))}</div>" for item in recommendations)
            + "</div>"
        )
    return "<div class='tight'>" + "".join(rows) + "</div>"


def render_compatibility(report: dict[str, Any]) -> str:
    compatibility = (report or {}).get("compatibility") or (report or {}).get("audio_replaced_compatibility") or {}
    matrix = compatibility.get("matrix") or []
    if not matrix:
        return "<div class='empty'>Build an MKV to see the player compatibility checklist.</div>"
    rows = "".join(
        f"<tr><td>{escape(str(item.get('player') or ''))}</td><td>{escape(str(item.get('platform') or ''))}</td>"
        f"<td><span class='badge'>{escape(str(item.get('expected') or ''))}</span></td><td class='compact'>{escape(str(item.get('notes') or ''))}</td></tr>"
        for item in matrix
    )
    warnings = "".join(f"<div class='badge warn'>{escape(str(item))}</div>" for item in compatibility.get("warnings") or [])
    return (
        f"<div class='tight'><div class='subtle'>Recommended: {escape(str(compatibility.get('recommended_player') or ''))}</div>"
        f"<table><thead><tr><th>Player</th><th>Platform</th><th>Expected</th><th>Notes</th></tr></thead><tbody>{rows}</tbody></table>{warnings}</div>"
    )


def render_status(status: dict[str, Any]) -> str:
    if not status:
        return "<div id='live-status' data-live-status class='empty'>No job history yet.</div>"
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
    return f"<div id='live-status' data-live-status class='subtle'>Live status enabled.</div><table><thead><tr><th>Time</th><th>Stage</th><th>State</th><th>Message</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


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


def render_select_options(values: list[str], selected_value: str) -> str:
    return "".join(
        f"<option value='{escape(value)}'{' selected' if value == selected_value else ''}>{escape(value)}</option>"
        for value in values
    )


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
