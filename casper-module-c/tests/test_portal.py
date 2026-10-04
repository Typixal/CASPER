"""Tests for the portal's per-replica capacity gate: queue, then refuse."""

import importlib
import threading
import time

import pytest


def load_portal(monkeypatch, *, max_concurrent, queue_timeout_ms, delay_ms):
    """Re-import the portal with the given capacity settings."""
    monkeypatch.setenv("MAX_CONCURRENT", str(max_concurrent))
    monkeypatch.setenv("QUEUE_TIMEOUT_MS", str(queue_timeout_ms))
    monkeypatch.setenv("MIN_DELAY_MS", str(delay_ms))
    monkeypatch.setenv("MAX_DELAY_MS", str(delay_ms))
    import app as portal

    return importlib.reload(portal)


def occupy_slot(portal):
    """Start a /results request in the background and return its thread."""
    thread = threading.Thread(target=lambda: portal.app.test_client().get("/results"))
    thread.start()
    time.sleep(0.05)  # let it take the slot
    return thread


def test_a_request_past_the_queue_timeout_is_refused_with_503(monkeypatch):
    portal = load_portal(monkeypatch, max_concurrent=1, queue_timeout_ms=50, delay_ms=400)
    busy = occupy_slot(portal)

    response = portal.app.test_client().get("/results")

    busy.join()
    assert response.status_code == 503


def test_a_queued_request_is_served_once_a_slot_frees(monkeypatch):
    portal = load_portal(monkeypatch, max_concurrent=1, queue_timeout_ms=2000, delay_ms=150)
    busy = occupy_slot(portal)

    started = time.perf_counter()
    response = portal.app.test_client().get("/results")
    waited = time.perf_counter() - started

    busy.join()
    assert response.status_code == 200
    # Queue wait + own work: latency grows under load.
    assert waited >= 0.2


def test_health_stays_fast_while_the_replica_is_saturated(monkeypatch):
    portal = load_portal(monkeypatch, max_concurrent=1, queue_timeout_ms=2000, delay_ms=500)
    busy = occupy_slot(portal)

    started = time.perf_counter()
    response = portal.app.test_client().get("/health")
    elapsed = time.perf_counter() - started

    busy.join()
    assert response.status_code == 200
    assert elapsed < 0.1


def test_the_503_body_says_the_replica_is_at_capacity(monkeypatch):
    portal = load_portal(monkeypatch, max_concurrent=1, queue_timeout_ms=50, delay_ms=400)
    busy = occupy_slot(portal)

    response = portal.app.test_client().get("/results")

    busy.join()
    assert response.get_json()["error"] == "replica at capacity"
