from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .mux_plan import ktv_mux_plan, replace_audio_plan
from .preflight import preflight_from_summary
from .track_roles import TRACK_ROLES, track_role_report
from .view_common import (
    audio_details,
    fmt,
    fmt_attr,
    fmt_percent,
    render_audio_options,
    render_select_options,
    song_url,
    trim,
)


def render_task_modes(
    song_id: str,
    summary: dict[str, Any],
    report: dict[str, Any],
    default_audio_order: str,
    default_duration_limit: str,
) -> str:
    selected_index = int((report or {}).get("selected_audio_index") or 0)
    keep_audio_index = int((report or {}).get("kept_audio_index") or 0)
    mix_ready = bool(summary.get("has_mix"))
    instrumental_ready = bool(summary.get("has_instrumental"))
    lyrics_ready = bool(summary.get("has_lyrics"))
    ass_ready = bool(summary.get("has_ass"))
    return f"""
<section class="panel module-launcher" id="tasks">
  <h2>Task Modes</h2>
  <div class="subtle">Pick one concrete task first. The advanced workbench below stays collapsed until you need every control.</div>
  <div class="task-grid">
    <div class="task-card">
      <strong>Only Make Instrumental</strong>
      <div class="subtle">Use this when you only want an audio file to inspect.</div>
      <form method="post" action="{song_url(song_id)}/run/extract" class="tight">
        <select name="audio_index">{render_audio_options(report, selected_index)}</select>
        <button class="secondary" type="submit">Extract Selected Track</button>
      </form>
      <form method="post" action="{song_url(song_id)}/run/separate-sample" class="tight">
        <input type="hidden" name="audio_index" value="{selected_index}">
        <input type="hidden" name="separation_preset" value="fast-review">
        <button class="secondary" type="submit">Try 30s Sample</button>
      </form>
      <form method="post" action="{song_url(song_id)}/run/separate"><button type="submit" {"disabled" if not mix_ready else ""}>Make Full Instrumental</button></form>
    </div>
    <div class="task-card">
      <strong>Replace Bad Track 2</strong>
      <div class="subtle">Remake accompaniment from a source track, then build an MKV with the original guide track plus the new accompaniment.</div>
      <form method="post" action="{song_url(song_id)}/run/remake-track" class="tight">
        <label>Separate source</label>
        <select name="audio_index">{render_audio_options(report, selected_index)}</select>
        <label>Keep original guide</label>
        <select name="keep_audio_index">{render_audio_options(report, keep_audio_index)}</select>
        <input type="hidden" name="copy_subtitles" value="1">
        <button type="submit">Remake + Replace</button>
      </form>
    </div>
    <div class="task-card">
      <strong>I Already Have Lyrics</strong>
      <div class="subtle">Paste or upload TXT, LRC, SRT, or ASS, then generate karaoke ASS.</div>
      <a class="button secondary" href="#lyrics">Open Subtitle Workbench</a>
      <form method="post" action="{song_url(song_id)}/run/align" class="tight">
        <select name="align_backend">{render_select_options(["auto", "lrc", "funasr", "simple"], "auto")}</select>
        <button class="secondary" type="submit" {"disabled" if not lyrics_ready else ""}>Generate ASS</button>
      </form>
    </div>
    <div class="task-card">
      <strong>I Already Have Instrumental</strong>
      <div class="subtle">Upload a WAV, AIFF, FLAC, or MP3. It will be rendered to the current instrumental.wav.</div>
      <form method="post" action="{song_url(song_id)}/instrumental-file" enctype="multipart/form-data" class="tight">
        <input name="file" type="file" accept="audio/*,.wav,.aiff,.flac,.mp3" required>
        <input name="label" value="external instrumental">
        <div class="fields">
          <div><label>Offset seconds</label><input name="offset" type="number" step="0.05" value="0"></div>
          <div><label>Gain dB</label><input name="gain_db" type="number" step="0.5" value="0"></div>
          <label class="checkbox-line"><input name="fit_to_mix" value="1" type="checkbox" checked> Fit to mix length</label>
          <label class="checkbox-line"><input name="normalize" value="1" type="checkbox"> Normalize</label>
        </div>
        <button class="secondary" type="submit">Use External Instrumental</button>
      </form>
      <span class="badge {'ok' if instrumental_ready else 'warn'}">{'ready' if instrumental_ready else 'needed'}</span>
    </div>
    <div class="task-card">
      <strong>Final KTV MKV</strong>
      <div class="subtle">Build only after source, instrumental, mix, and ASS are ready.</div>
      <form method="post" action="{song_url(song_id)}/run/mux" class="tight">
        <select name="audio_order">{render_select_options(["instrumental-first", "original-first"], default_audio_order)}</select>
        <input name="duration_limit" type="number" min="0" step="1" value="{default_duration_limit}" placeholder="seconds">
        <button type="submit" {"disabled" if not (instrumental_ready and mix_ready and ass_ready) else ""}>Build KTV MKV</button>
      </form>
    </div>
    <div class="task-card">
      <strong>Support Package</strong>
      <div class="subtle">Export reports, lyrics, takes, and optional logs when a result needs review.</div>
      <a class="button secondary" href="{song_url(song_id)}/export">Export Package</a>
      <a class="button secondary" href="#preflight">Check Preflight</a>
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
  {render_failure_playbook(failed_stage)}
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
    <a class="button secondary" href="{song_url(song_id)}/export?include_logs=1">Export Support Package</a>
  </div>
</section>
"""

def render_failure_playbook(stage: str) -> str:
    playbooks = {
        "probe": ["Confirm the source file opens in VLC/IINA.", "Re-import the file if FFprobe reports no streams."],
        "preview-tracks": ["Run Probe again.", "Use a shorter preview duration if the file is remote or damaged."],
        "extract": ["Choose an existing source audio track.", "Use Source Tracks to confirm Track 1/Track 2 before extraction."],
        "separate": ["Try a 30-second sample first.", "Retry on CPU if MPS/CUDA fails.", "Try another source track or preset."],
        "separate-sample": ["Move the sample start time to a chorus.", "Retry with CPU or a shorter duration."],
        "align": ["Confirm lyrics.txt is not empty.", "Use LRC/SRT/ASS if you already have timestamps."],
        "mux": ["Check Preflight for missing instrumental, mix, or lyrics.ass.", "Use a short duration limit to isolate mux issues."],
        "replace-audio": ["Check that instrumental.wav exists.", "Choose which original track to keep as the guide track."],
        "normalize": ["Confirm instrumental.wav exists.", "Try a less aggressive loudness target."],
    }
    steps = playbooks.get(stage)
    if not steps:
        return ""
    items = "".join(f"<li>{escape(step)}</li>" for step in steps)
    return f"<div class='compact'><strong>Suggested recovery</strong><ol>{items}</ol></div>"

def render_ab_review(song_id: str, summary: dict[str, Any], takes: list[dict[str, Any]]) -> str:
    rows = []
    if summary.get("has_mix"):
        rows.append(
            f"<div><strong>A Original Mix</strong><audio data-sync-player controls src='{song_url(song_id)}/audio/mix'></audio></div>"
        )
    if summary.get("has_instrumental"):
        rows.append(
            f"<div><strong>B Current Instrumental</strong><audio data-sync-player controls src='{song_url(song_id)}/audio/instrumental'></audio></div>"
        )
    instrumental_takes = [take for take in takes if take.get("kind") == "instrumental"][:4]
    for take in instrumental_takes:
        filename = str(take.get("filename") or "")
        encoded = quote(filename, safe="")
        score_value = "" if take.get("score") is None else str(take.get("score"))
        rows.append(
            f"<div class='take-row'><div class='row'><strong>Saved Instrumental Take</strong><span class='badge'>{escape(score_value or 'unscored')}</span></div>"
            f"<audio data-sync-player controls src='{song_url(song_id)}/download/take/{encoded}'></audio>"
            f"<form method='post' action='{song_url(song_id)}/take/{encoded}/update' class='row'>"
            f"<input name='label' value='{escape(str(take.get('label') or ''))}' placeholder='label'>"
            f"<input name='note' value='{escape(str(take.get('note') or ''))}' placeholder='listening note'>"
            f"<input class='number-input' name='score' type='number' min='1' max='5' value='{escape(score_value)}' placeholder='1-5'>"
            "<button class='secondary' type='submit'>Save Review</button></form></div>"
        )
    if not rows:
        return "<div class='empty'>Generate mix and instrumental audio to compare takes.</div>"
    controls = (
        "<div class='row'><button class='secondary' type='button' data-sync-review>Sync Visible Players</button>"
        "<span class='subtle'>Play one review track, then sync the others to the same timestamp.</span></div>"
    )
    return "<div class='tight sync-review'>" + controls + "".join(rows) + "</div>"

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
        badges = track_decision_badges(report, audio_index, stream)
        role = track_role_report(report, audio_index, stream)
        role_select = render_select_options(TRACK_ROLES, str(role["role"]))
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
            f"<div><strong>Track {audio_index + 1}</strong><div class='subtle'>CLI --audio-index {audio_index}</div>{badges}"
            f"<div class='subtle'>{escape(str(role['label']))} · {escape(str(role['source']))}</div></div>"
            f"<div class='compact'>{escape(details)}</div>"
            f"<div>{player}<div class='row track-actions'>"
            f"<form method='post' action='{song_url(song_id)}/run/extract'><input type='hidden' name='audio_index' value='{audio_index}'><button class='secondary' type='submit'>Use Track {audio_index + 1} For Extract</button></form>"
            f"<form method='post' action='{song_url(song_id)}/run/separate-sample'><input type='hidden' name='audio_index' value='{audio_index}'><input type='hidden' name='separation_preset' value='fast-review'><button class='secondary' type='submit'>Try Track {audio_index + 1}</button></form>"
            f"<form method='post' action='{song_url(song_id)}/run/remake-track'><input type='hidden' name='audio_index' value='{audio_index}'><input type='hidden' name='keep_audio_index' value='0'><input type='hidden' name='copy_subtitles' value='1'><button class='secondary' type='submit'>Remake From Track {audio_index + 1}</button></form>"
            f"<form method='post' action='{song_url(song_id)}/track-role' class='track-role-form'><input type='hidden' name='audio_index' value='{audio_index}'><select name='role'>{role_select}</select><input name='note' value='{escape(str(role.get('note') or ''))}' placeholder='role note'><button class='secondary' type='submit'>Save Role</button></form>"
            "</div></div>"
            "</div>"
        )
    subtitle_panel = render_subtitle_tracks(song_id, report)
    return "<div class='tight'>" + "".join(rows) + subtitle_panel + "</div>"

def track_decision_badges(report: dict[str, Any], audio_index: int, stream: dict[str, Any]) -> str:
    badges = []
    selected = (report or {}).get("selected_audio_index")
    kept = (report or {}).get("kept_audio_index")
    remade = (report or {}).get("remade_from_audio_track")
    if (stream.get("disposition") or {}).get("default"):
        badges.append("<span class='badge ok'>source default</span>")
    if selected is not None and int(selected) == audio_index:
        badges.append("<span class='badge ok'>selected for separation</span>")
    if kept is not None and int(kept) == audio_index:
        badges.append("<span class='badge'>kept as guide</span>")
    if remade is not None and int(remade) == audio_index + 1:
        badges.append("<span class='badge warn'>last remake source</span>")
    if not badges:
        badges.append("<span class='badge'>candidate</span>")
    return "<div class='row' style='margin-top:6px;'>" + "".join(badges) + "</div>"

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
    for index, item in enumerate(lines):
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
    return f"""
      <div class="tight" style="margin-top:14px;">
        <h3>Subtitle Timing</h3>
        <audio class="subtitle-player" data-subtitle-player controls src="{song_url(song_id)}/audio/instrumental"></audio>
        <div class="row"><button class="secondary" type="button" data-use-playhead>Use Playhead For Focused Time</button><span class="subtle">Click a time input, play audio, then copy the current playhead.</span></div>
        <img class="waveform" data-duration="{fmt_attr(max_time)}" src="{song_url(song_id)}/waveform.svg" alt="Audio waveform">
        <form method="post" action="{song_url(song_id)}/alignment" class="tight">
          <input type="hidden" name="line_count" value="{len(lines)}">
          {''.join(rows)}
          <div><button class="secondary" type="submit">Save Subtitle Edits</button></div>
        </form>
        <form method="post" action="{song_url(song_id)}/alignment-shift-lines" class="row">
          <input class="number-input" name="start_line" type="number" min="1" value="1">
          <input class="number-input" name="end_line" type="number" min="1" value="{len(lines)}">
          <input class="number-input" name="seconds" type="number" step="0.05" value="0">
          <button class="secondary" type="submit">Shift Lines</button>
        </form>
        <form method="post" action="{song_url(song_id)}/alignment-stretch-lines" class="row">
          <input class="number-input" name="start_line" type="number" min="1" value="1">
          <input class="number-input" name="end_line" type="number" min="1" value="{len(lines)}">
          <input class="number-input" name="target_start" type="number" step="0.05" value="{fmt_attr((lines[0] or {}).get('start'))}">
          <input class="number-input" name="target_end" type="number" step="0.05" value="{fmt_attr((lines[-1] or {}).get('end'))}">
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
    kind = str(take.get("kind") or "")
    promote = (
        f"<form class='mini-form' method='post' action='{song_url(song_id)}/take/{encoded}/set-current'><button class='secondary' type='submit'>Set Current</button></form>"
        if kind in {"instrumental", "audio-replaced", "ktv"}
        else ""
    )
    return f"""
<div class="take-row">
  <div class="row"><strong>Saved Take</strong>{current}<span class="badge">{escape(kind)}</span><span class="badge">{escape(score_value or "unscored")}</span></div>
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
    {promote}
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

def render_preflight(summary: dict[str, Any], report: dict[str, Any]) -> str:
    preflight = preflight_from_summary(summary, report)
    rows = "".join(
        "<div class='preflight-item'>"
        f"<div><strong>{escape(str(item['label']))}</strong><div class='subtle'>{escape(str(item['hint']))}</div></div>"
        f"<span class='badge {'ok' if item['ready'] else 'warn'}'>{'ready' if item['ready'] else 'missing'}</span>"
        "</div>"
        for item in preflight["items"]
    )
    state = (
        f"<div class='row' style='margin-bottom:10px;'>"
        f"<span class='badge {'ok' if preflight['ok_for_sample_review'] else 'warn'}'>sample review</span>"
        f"<span class='badge {'ok' if preflight['ok_for_instrumental_review'] else 'warn'}'>instrumental review</span>"
        f"<span class='badge {'ok' if preflight['ok_for_replace_audio'] else 'warn'}'>replace audio</span>"
        f"<span class='badge {'ok' if preflight['ok_for_final_mkv'] else 'warn'}'>final MKV</span>"
        "</div>"
    )
    warnings = preflight["warnings"]
    warning_html = ""
    if warnings:
        warning_html = (
            "<div class='tight' style='margin-top:10px;'>"
            + "".join(f"<div class='badge warn'>{escape(trim(item, 180))}</div>" for item in list(dict.fromkeys(warnings))[:8])
            + "</div>"
        )
    else:
        warning_html = "<div class='subtle' style='margin-top:10px;'>No blocking preflight warnings recorded yet.</div>"
    return f"{state}<div class='preflight-grid'>{rows}</div>{warning_html}"

def render_mux_plan(summary: dict[str, Any], report: dict[str, Any], audio_order: str, keep_audio_index: int) -> str:
    ktv_plan = ktv_mux_plan(summary, report, audio_order=audio_order)
    replace_plan = replace_audio_plan(summary, report, keep_audio_index=keep_audio_index, copy_subtitles=True)
    return (
        "<div class='tight'>"
        + render_plan_block("Final KTV MKV", ktv_plan)
        + render_plan_block("Replace Track 2 MKV", replace_plan)
        + "</div>"
    )

def render_plan_block(title: str, plan: dict[str, Any]) -> str:
    state = "ok" if plan.get("ready") else "warn"
    audio_rows = "".join(
        f"<tr><td>{escape(str(item.get('track') or ''))}</td><td>{escape(str(item.get('source') or ''))}</td>"
        f"<td>{escape(str(item.get('title') or ''))}</td><td>{'yes' if item.get('default') else 'no'}</td>"
        f"<td>{escape(str(item.get('role') or ''))}</td></tr>"
        for item in plan.get("audio") or []
    )
    subtitles = ", ".join(str(item.get("source") or "") for item in plan.get("subtitles") or []) or "none"
    warnings = "".join(f"<span class='badge warn'>{escape(trim(str(item), 160))}</span>" for item in plan.get("warnings") or [])
    return f"""
<div class="take-row">
  <div class="row"><strong>{escape(title)}</strong><span class="badge {state}">{'ready' if plan.get('ready') else 'check'}</span></div>
  <div class="compact">Video: {escape(str(plan.get('video') or 'source video'))}; Subtitles: {escape(subtitles)}</div>
  <table><thead><tr><th>Track</th><th>Source</th><th>Title</th><th>Default</th><th>Role</th></tr></thead><tbody>{audio_rows}</tbody></table>
  <div class="row">{warnings}</div>
</div>
"""

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
