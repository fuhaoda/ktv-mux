from __future__ import annotations

from html import escape
from typing import Any

from .recipes import RECIPE_STAGES
from .separation_presets import PRESETS
from .view_admin import (
    render_doctor,
    render_doctor_summary,
    render_import_confirm,
    render_job_detail,
    render_jobs,
    render_logs,
    render_roadmap,
    render_settings,
    render_storage,
    render_wizard,
)
from .view_common import (
    compact_report,
    fmt_attr,
    json_dump,
    page,
    render_audio_options,
    render_delete_confirm,
    render_error,
    render_flags,
    render_select_options,
    song_url,
)
from .view_song import (
    render_ab_review,
    render_alignment_editor,
    render_audio_blocks,
    render_compatibility,
    render_duplicate_warning,
    render_failure_recovery,
    render_lyrics_versions,
    render_metadata_form,
    render_mux_plan,
    render_next_actions,
    render_outputs,
    render_preflight,
    render_quality,
    render_status,
    render_task_modes,
    render_track_panel,
)

__all__ = [
    "page",
    "render_delete_confirm",
    "render_detail",
    "render_doctor",
    "render_error",
    "render_import_confirm",
    "render_index",
    "render_job_detail",
    "render_roadmap",
    "render_settings",
    "render_storage",
    "render_wizard",
    "song_url",
]


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
    <form method="post" action="/batch-recipe" class="row" style="margin-bottom:10px;">
      <select name="recipe">{render_select_options(sorted(RECIPE_STAGES), "instrumental-review")}</select>
      <input class="number-input" name="audio_index" type="number" min="0" value="0" title="zero-based audio index">
      <select name="separation_preset">{render_select_options(sorted(PRESETS), "fast-review")}</select>
      <label class="checkbox-line"><input name="dry_run" value="1" type="checkbox"> Dry run</label>
      <button class="secondary" type="submit">Queue Recipe</button>
    </form>
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
{render_task_modes(song_id, summary, report, default_audio_order, default_duration_limit)}
<nav class="workflow-tabs">
  <a href="#tasks">Tasks</a>
  <a href="#tracks">Tracks</a>
  <a href="#audio">Audio</a>
  <a href="#lyrics">Lyrics</a>
  <a href="#preflight">Preflight</a>
  <a href="#mux">Mux</a>
  <a href="#outputs">Outputs</a>
  <a href="#jobs">Jobs</a>
</nav>
<details class="advanced-workbench">
  <summary>Advanced Workbench</summary>
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
          <input class="number-input" name="offset" type="number" step="0.05" value="0" title="positive delays, negative trims">
          <input class="number-input" name="gain_db" type="number" step="0.5" value="0" title="gain dB">
          <label class="checkbox-line"><input name="fit_to_mix" value="1" type="checkbox"> Fit to mix</label>
          <label class="checkbox-line"><input name="normalize" value="1" type="checkbox"> Normalize</label>
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
    <div class="panel" id="preflight">
      <h2>Preflight</h2>
      {render_preflight(summary, report)}
    </div>
    <div class="panel">
      <h2>Mux Preview</h2>
      {render_mux_plan(summary, report, default_audio_order, keep_audio_index)}
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
</details>
"""
