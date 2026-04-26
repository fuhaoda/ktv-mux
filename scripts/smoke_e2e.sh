#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KTV_BIN="${KTV_BIN:-$ROOT/.venv/bin/ktv}"
ASSET="${ASSET:-$ROOT/assets/朋友-周华健.mkv}"
WORK="${WORK:-$(mktemp -d "${TMPDIR:-/tmp}/ktv-smoke.XXXXXX")}"
LIBRARY="$WORK/library"
SONG_ID="朋友-周华健"

if [ ! -x "$KTV_BIN" ]; then
  echo "ktv executable not found: $KTV_BIN" >&2
  exit 1
fi
if [ ! -f "$ASSET" ]; then
  echo "sample asset not found: $ASSET" >&2
  exit 1
fi

command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null

cat > "$WORK/lyrics.lrc" <<'LYRICS'
[00:00.50]朋友一生一起走
[00:02.00]那些日子不再有
LYRICS

"$KTV_BIN" --library "$LIBRARY" import "$ASSET"
"$KTV_BIN" --library "$LIBRARY" lyrics "$SONG_ID" "$WORK/lyrics.lrc"
"$KTV_BIN" --library "$LIBRARY" probe "$SONG_ID"
"$KTV_BIN" --library "$LIBRARY" preview-tracks "$SONG_ID" --preset chorus --count 2 --duration 2
"$KTV_BIN" --library "$LIBRARY" extract "$SONG_ID" --audio-index 0
"$KTV_BIN" --library "$LIBRARY" align "$SONG_ID" --backend lrc

ffmpeg -y -hide_banner -t 3 -i "$LIBRARY/work/$SONG_ID/mix.wav" -af volume=0.5 -c:a pcm_s16le "$LIBRARY/output/$SONG_ID/instrumental.wav" >/dev/null 2>&1
"$KTV_BIN" --library "$LIBRARY" mux "$SONG_ID" --duration-limit 3

ffprobe -hide_banner -v error -show_streams -of json "$LIBRARY/output/$SONG_ID/$SONG_ID.ktv.mkv" > "$WORK/probe.json"
python3 - "$WORK/probe.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
streams = data.get("streams") or []
video = [s for s in streams if s.get("codec_type") == "video"]
audio = [s for s in streams if s.get("codec_type") == "audio"]
subtitle = [s for s in streams if s.get("codec_type") == "subtitle"]
assert len(video) == 1, len(video)
assert len(audio) == 2, len(audio)
assert len(subtitle) == 1, len(subtitle)
PY

echo "smoke_e2e ok: $LIBRARY/output/$SONG_ID/$SONG_ID.ktv.mkv"
