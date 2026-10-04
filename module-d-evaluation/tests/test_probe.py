"""Tests for the latency probe the reactive baseline scales on."""

import pytest

import probe


def test_p95_of_twenty_samples_is_the_nineteenth_smallest():
    samples = list(range(1, 21))  # 1..20 ms

    assert probe.percentile(samples, 95) == 19


def test_percentile_of_a_single_sample_is_that_sample():
    assert probe.percentile([42.0], 95) == 42.0


def test_percentile_ignores_input_order():
    assert probe.percentile([300, 10, 200, 20, 100], 50) == 100


def test_percentile_of_no_samples_is_an_error():
    # An empty probe round means every request failed or none were sent --
    # reporting 0 ms would tell the scaler everything is fast.
    with pytest.raises(ValueError):
        probe.percentile([], 95)


# --- measure(): real HTTP against a real local server ------------------------

import http.server  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200
    delay_s = 0.0

    def do_GET(self):
        time.sleep(self.delay_s)
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture
def server():
    """A real HTTP server on a free port, configurable per test."""
    handler = type("Handler", (_Handler,), {})
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield handler, "http://127.0.0.1:{}/results".format(httpd.server_address[1])
    httpd.shutdown()


def test_measure_returns_one_latency_per_request(server):
    _, url = server

    result = probe.measure(url, requests=4, timeout_s=2)

    assert len(result.latencies_ms) == 4
    assert result.errors == 0


def test_measure_reflects_how_slow_the_server_is(server):
    handler, url = server
    handler.delay_s = 0.2

    result = probe.measure(url, requests=3, timeout_s=2)

    assert min(result.latencies_ms) >= 200


def test_a_503_counts_as_an_error_and_as_a_timeout_length_latency(server):
    # An overloaded portal refusing requests is the strongest overload signal
    # there is. Recording its (fast) refusal time would make overload look
    # like great latency, so a failure is scored at the full timeout.
    handler, url = server
    handler.status = 503

    result = probe.measure(url, requests=2, timeout_s=1.5)

    assert result.errors == 2
    assert result.latencies_ms == [1500.0, 1500.0]


def test_an_unreachable_portal_counts_every_request_as_an_error():
    result = probe.measure("http://127.0.0.1:1/results", requests=2, timeout_s=0.5)

    assert result.errors == 2
