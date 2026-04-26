# Usage

## Start The App

One-click macOS:

```bash
cd /Users/hfu@amgen.com/Documents/MyGit/ktv-mux
scripts/bootstrap_mac.sh
scripts/ktv-start.command
```

Optional Desktop launcher:

```bash
make launcher
```

Manual setup:

```bash
cd /Users/hfu@amgen.com/Documents/MyGit/ktv-mux
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[web,dev,separation]"
.venv/bin/ktv --library library serve --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Fast Test With The Bundled MKV

```bash
.venv/bin/ktv import assets/朋友-周华健.mkv
.venv/bin/ktv metadata 朋友-周华健 --title "朋友" --artist "周华健"
.venv/bin/ktv probe 朋友-周华健
.venv/bin/ktv preview-tracks 朋友-周华健 --start 30 --duration 20 --count 2 --spacing 45
.venv/bin/ktv extract 朋友-周华健 --audio-index 0
.venv/bin/ktv separate 朋友-周华健 --model htdemucs --device auto
```

Output:

```text
library/output/朋友-周华健/instrumental.wav
```

## Track Numbering

The Web UI shows `Track 1`, `Track 2`, etc.

The CLI uses zero-based indexes:

```bash
ktv extract 朋友-周华健 --audio-index 0  # Web Track 1
ktv extract 朋友-周华健 --audio-index 1  # Web Track 2
```

Before extracting, use `preview-tracks` or the Web `Preview Tracks` button to create playable clips for every source audio track. `--start` is useful when the first seconds are silence, applause, or an intro.

Set defaults used by the Web forms:

```bash
ktv settings --preview-start 30 --preview-duration 20 --preview-count 2 --demucs-model htdemucs --demucs-device auto --worker-count 2 --auto-refresh-seconds 3
```

The Web Settings page exposes the same values. Worker count applies when the Web app starts.

Use `--preset chorus` when you want preview clips around the middle/chorus area instead of the intro:

```bash
ktv preview-tracks 朋友-周华健 --preset chorus --count 3 --duration 12
```

## Replace Track 2 With A Generated Instrumental

After `separate` creates `instrumental.wav`:

```bash
ktv replace-audio 朋友-周华健 --keep-audio-index 0
```

Output:

```text
library/output/朋友-周华健/朋友-周华健.audio-replaced.mkv
```

This output keeps the source video, keeps original Track 1 as `原唱`, writes the generated instrumental as Track 2 `伴奏`, and copies source subtitles when present.

Normalize the generated instrumental before using it:

```bash
ktv normalize 朋友-周华健 --target-i -16
ktv normalize 朋友-周华健 --target-i -16 --replace-current
```

The first command creates `instrumental.normalized.wav`; the second promotes it to `instrumental.wav`.

## Inspect Separation

After `separate`, the app writes:

```text
library/output/朋友-周华健/instrumental.wav
library/work/朋友-周华健/vocals.wav
library/work/朋友-周华健/logs/separate.log
library/work/朋友-周华健/track-previews/track-1.wav
library/output/朋友-周华健/report.json
library/output/朋友-周华健/takes/
```

The Web detail page shows playable audio, recent job state, the Demucs log link, track previews, editable versioned takes, waveform/timeline subtitle editing, and WAV level metrics including clipping, silence ratio, and recommendations.

CLI take management:

```bash
ktv takes 朋友-周华健
ktv take-note 朋友-周华健 instrumental.20260425T010101Z.wav --label "good take" --note "less vocal bleed"
ktv take-current 朋友-周华健 instrumental.20260425T010101Z.wav
ktv take-delete 朋友-周华健 instrumental.20260425T010101Z.wav
```

Export a review package:

```bash
ktv export 朋友-周华健 --include-logs
ktv export 朋友-周华健 --no-audio --no-takes
```

Output:

```text
library/output/朋友-周华健/朋友-周华健.package.zip
```

The package includes current outputs, reports, lyrics/subtitles, alignment, and saved takes by default. Flags can exclude large audio/MKV/take files or include logs.

## Full KTV MKV With Lyrics

Add lyrics:

```bash
ktv lyrics 朋友-周华健 path/to/lyrics.txt
ktv align 朋友-周华健 --backend simple
ktv shift 朋友-周华健 --seconds 0.25
ktv edit-line 朋友-周华健 --index 0 --start 8.5 --end 11.2 --text "朋友一生一起走"
ktv mux 朋友-周华健
```

The `simple` backend creates draft timings without downloading alignment models. Install the full ML extra when you want FunASR:

```bash
.venv/bin/python -m pip install -e ".[ml]"
ktv align 朋友-周华健 --backend funasr
```

Use a positive shift when subtitles appear too early; use a negative shift when they appear too late. The Web detail page also exposes a line-level timing editor after `align` creates `alignment.json`.

LRC timestamps become initial subtitle timing when lyrics are saved; simple chord tags are cleaned from the stored `lyrics.txt`:

```text
[00:01.00][C]  第一  句　歌词
```

becomes:

```text
第一 句 歌词
```

and writes draft timing to:

```text
library/work/{song_id}/alignment.json
```

## Jobs And Diagnostics

The Web UI has a local job drawer with progress bars, queued/running-job cancel, failed/canceled-job retry, and finished-job pruning. Demucs progress is estimated from `separate.log`; URL download progress is estimated from `import.log`.

CLI job inspection:

```bash
ktv jobs
ktv jobs-prune
```

Next-action hints:

```bash
ktv next 朋友-周华健
```

Batch import local files:

```bash
ktv import-many ~/Movies/song1.mkv ~/Movies/song2.mkv
```

Batch one stage across the library:

```bash
ktv batch-stage probe
ktv batch-stage preview-tracks --preset chorus --count 2
ktv batch-stage extract --audio-index 0
ktv batch-stage separate --model htdemucs --device auto
```

Run local diagnostics:

```bash
ktv doctor
ktv doctor 朋友-周华健
```

## Cleanup

Regenerable work files can be removed without deleting the source or final output:

```bash
ktv clean-work 朋友-周华健
```

Delete a song from the library:

```bash
ktv delete 朋友-周华健
```

The Web UI exposes both actions from the song detail page. Delete requires typing the exact song ID.
