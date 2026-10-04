"""Tests for the dashboard's probe controls.

During Module D's experiment the dashboard's own latency probe must not add
traffic to the very thing being measured. Starting it switched off is not
enough -- one click on the masthead button turned it back on mid-run. So
-Compare also LOCKS it.
"""

import importlib

import pytest


def load_app(monkeypatch, probe="1", locked=None):
    monkeypatch.setenv("CASPER_DASH_PROBE", probe)
    if locked is None:
        monkeypatch.delenv("CASPER_DASH_PROBE_LOCKED", raising=False)
    else:
        monkeypatch.setenv("CASPER_DASH_PROBE_LOCKED", locked)
    import app

    return importlib.reload(app)


def test_the_toggle_flips_the_probe_when_unlocked(monkeypatch):
    dash = load_app(monkeypatch, probe="1")

    response = dash.app.test_client().post("/api/probe/toggle")

    assert response.get_json()["probe_enabled"] is False


def test_a_locked_probe_cannot_be_switched_back_on(monkeypatch):
    dash = load_app(monkeypatch, probe="0", locked="1")

    response = dash.app.test_client().post("/api/probe/toggle")

    assert response.status_code == 409
    assert dash.probe_enabled() is False


def test_the_lock_is_reported_so_the_ui_can_disable_the_button(monkeypatch):
    dash = load_app(monkeypatch, probe="0", locked="1")

    assert dash.probe_locked() is True


# --- Module D result charts ------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


@pytest.fixture
def results_app(monkeypatch, tmp_path):
    import collector

    (tmp_path / "latency_over_time.png").write_bytes(PNG)
    (tmp_path / "comparison.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(collector, "MODULE_D_RESULTS_DIR", tmp_path)
    return load_app(monkeypatch).app.test_client()


def test_a_result_chart_is_served_as_a_png(results_app):
    response = results_app.get("/api/results/latency_over_time.png")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data == PNG


def test_only_png_charts_are_served(results_app):
    # The route exists to show the report's charts, not to expose files.
    assert results_app.get("/api/results/comparison.json").status_code == 404


def test_paths_outside_the_results_folder_are_refused(results_app):
    assert results_app.get("/api/results/..%2Fapp.png").status_code == 404
    assert results_app.get("/api/results/../app.png").status_code == 404


def test_a_missing_chart_is_a_404_not_a_crash(results_app):
    assert results_app.get("/api/results/nope.png").status_code == 404
