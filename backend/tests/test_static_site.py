"""Single-process demo hosting: the built UI is served from the same origin
as the API by backend/app/static_site.py, so one URL is the whole product."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.static_site import dist_dir, mount_static_site


def _mini_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_static_site_is_skipped_without_a_build(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("FLARE_STATIC_DIR", str(tmp_path / "missing"))
    assert dist_dir() is None
    app = _mini_app()
    assert mount_static_site(app) is None
    # No "/" route: the API-only process still answers its own routes.
    assert TestClient(app).get("/api/ping").json() == {"status": "ok"}


def test_static_site_serves_index_and_assets(
    tmp_path: Path, monkeypatch,
) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>FLARE</title>",
                                         encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setenv("FLARE_STATIC_DIR", str(tmp_path))

    app = _mini_app()
    assert mount_static_site(app) == tmp_path.resolve()
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert "FLARE" in root.text
    assert client.get("/assets/app.js").status_code == 200
    # The API keeps precedence over the catch-all static mount.
    assert client.get("/api/ping").json() == {"status": "ok"}
    # A path that is neither an asset nor the index is a 404, not the UI.
    assert client.get("/nope.js").status_code == 404


def test_shipped_build_is_served_when_present() -> None:
    """When a build exists in this checkout, the real app must serve it."""
    from backend.app.main import app

    if dist_dir() is None:  # API-only checkout (no `npm run build` yet)
        return
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200
