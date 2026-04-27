import socket
import threading
import time

import pytest

from ktv_mux.paths import LibraryPaths
from ktv_mux.web import create_app


@pytest.mark.browser
def test_playwright_homepage_smoke(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    library = LibraryPaths(tmp_path / "library")
    library.ensure_song_dirs("song")
    (library.raw_dir("song") / "source.mkv").write_bytes(b"sample")
    library.report_json("song").write_text(
        '{"probe":{"streams":[{"codec_type":"audio","codec_name":"aac","channels":2,"sample_rate":"44100"}]}}',
        encoding="utf-8",
    )
    library.status_json("song").write_text(
        '{"history":[{"time":"2026-04-26T00:00:00+00:00","stage":"probe","state":"completed","message":"completed"}]}',
        encoding="utf-8",
    )
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(library),
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server(port)

    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            assert page.locator("text=First Run Wizard").first.is_visible()
            assert page.locator("text=Choose File").first.is_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            for path in ["/", "/doctor", "/songs/song"]:
                page.goto(f"http://127.0.0.1:{port}{path}", wait_until="networkidle")
                overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                assert overflow <= 1
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(port: int) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError("uvicorn test server did not start")
