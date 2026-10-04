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
