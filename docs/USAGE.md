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

## Full KTV MKV With Lyrics

Add lyrics:

```bash
ktv lyrics 朋友-周华健 path/to/lyrics.txt
ktv align 朋友-周华健 --backend simple
ktv mux 朋友-周华健
```

The `simple` backend creates draft timings without downloading alignment models. Install the full ML extra when you want FunASR:

```bash
.venv/bin/python -m pip install -e ".[ml]"
ktv align 朋友-周华健 --backend funasr
```

