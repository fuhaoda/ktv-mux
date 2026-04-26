# Roadmap And Product Boundaries

## v1 Scope

- Local-first library under `library/`.
- Import local media, upload media, scan `library/inbox`, or queue a rights-confirmed URL download.
- Probe tracks, preview tracks, extract one source audio track, run Demucs separation, normalize, and review takes.
- Run modules independently: short sample separation, external instrumental import, embedded subtitle extraction, track remake, replace-audio, and mux.
- Save plain text, LRC, SRT, or ASS lyrics; generate or import timed ASS karaoke subtitles.
- Mux KTV MKV with original video, instrumental audio, original mix audio, and ASS subtitles.
- Export a support bundle containing reports, optional logs, Doctor output, settings, storage, and environment metadata.

## v2 Candidates

- Better forced alignment backends and automatic lyric extraction/search.
- Richer waveform subtitle editing with zoom, snapping, and batch retiming.
- Packaged desktop app with a signed macOS bundle.
- Browser-level regression tests in CI with Playwright browsers installed.
- More configurable output naming and multi-format export presets.

## Non-Goals

- No DRM bypass, access-control bypass, or copyright-evasion workflow.
- No hosted cloud media library.
- No mandatory Node frontend for v1.
- No guarantee that QuickTime Player will support every MKV/ASS output.
