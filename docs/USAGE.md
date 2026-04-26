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
library/output/朋友-周华健/report.json
```

The Web detail page shows playable audio, recent job state, the Demucs log link, and basic WAV level metrics.

## Full KTV MKV With Lyrics

Add lyrics:

```bash
ktv lyrics 朋友-周华健 path/to/lyrics.txt
ktv align 朋友-周华健 --backend simple
ktv shift 朋友-周华健 --seconds 0.25
ktv mux 朋友-周华健
```

The `simple` backend creates draft timings without downloading alignment models. Install the full ML extra when you want FunASR:

```bash
.venv/bin/python -m pip install -e ".[ml]"
ktv align 朋友-周华健 --backend funasr
```

Use a positive shift when subtitles appear too early; use a negative shift when they appear too late.

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
