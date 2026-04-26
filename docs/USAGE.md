# Usage

## Start The App

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
.venv/bin/ktv probe 朋友-周华健
.venv/bin/ktv preview-tracks 朋友-周华健
.venv/bin/ktv extract 朋友-周华健 --audio-index 0
.venv/bin/ktv separate 朋友-周华健
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

Before extracting, use `preview-tracks` or the Web `Preview Tracks` button to create short playable clips for every source audio track.

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

The Web detail page shows playable audio, recent job state, the Demucs log link, track previews, versioned takes, and WAV level metrics including clipping and silence ratio.

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

LRC timestamps and simple chord tags are cleaned when lyrics are saved:

```text
[00:01.00][C]  第一  句　歌词
```

becomes:

```text
第一 句 歌词
```

## Jobs And Diagnostics

The Web UI has a local job drawer with progress bars, queued-job cancel, and failed-job retry. Demucs progress is estimated from `separate.log`.

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
