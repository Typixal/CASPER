"""Module D -- comparison charts for the Phase I report.

Colours follow the project's architecture diagram: steel for CASPER's
predictive strategy, amber for the reactive baseline.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only; no display needed
import matplotlib.pyplot as plt  # noqa: E402

STEEL = "#4A6FA5"
AMBER = "#F2994A"
NAVY = "#16213E"
COLORS = {"predictive": STEEL, "reactive": AMBER}
LABELS = {"predictive": "Predictive (CASPER)", "reactive": "Reactive baseline"}


def _replica_steps(events, initial, end_s):
    """(x, y) for a step plot of replica count over the run."""
    xs, ys = [0.0], [initial]
    for event in sorted(events, key=lambda e: e["t"]):
        xs.append(event["t"])
        ys.append(event["replicas"])
    xs.append(end_s)
    ys.append(ys[-1])
    return xs, ys


def _latency_over_time(comparison, path, ramp_start_s, initial_replicas):
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(10, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 2]}
    )

    end_s = 0.0
    for name in ("reactive", "predictive"):
        buckets = comparison["strategies"][name]["series"]["buckets"]
        # Skip empty intervals rather than plotting them as 0 ms.
        points = [(b["t"], b["p95_ms"]) for b in buckets if b["p95_ms"] is not None]
        if points:
            xs, ys = zip(*points)
            top.plot(xs, ys, color=COLORS[name], linewidth=2.2, label=LABELS[name])
            end_s = max(end_s, max(xs))

    for name in ("reactive", "predictive"):
        events = comparison["strategies"][name]["events"]
        xs, ys = _replica_steps(events, initial_replicas, end_s)
        bottom.step(xs, ys, where="post", color=COLORS[name], linewidth=2.2, label=LABELS[name])

    for axis in (top, bottom):
        axis.axvline(ramp_start_s, color=NAVY, linestyle="--", linewidth=1.2, alpha=0.7)
        axis.grid(alpha=0.25)
    top.text(ramp_start_s, top.get_ylim()[1] * 0.95, "  traffic ramp starts",
             color=NAVY, fontsize=9, va="top")

    top.set_ylabel("p95 response time (ms)")
    top.set_title("Same traffic, two scaling strategies", color=NAVY, fontweight="bold")
    top.legend(loc="upper right")
    bottom.set_ylabel("healthy replicas")
    bottom.set_xlabel("seconds into the run")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _summary_bars(comparison, path):
    names = ("reactive", "predictive")
    panels = [
        ("p95 response time (ms)", lambda r: r["summary"]["p95_ms"]),
        ("error rate (%)", lambda r: r["summary"]["error_rate"] * 100.0),
        ("successful requests (%)", lambda r: r["summary"]["success_pct"]),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    for axis, (title, getter) in zip(axes, panels):
        values = [getter(comparison["strategies"][n]) for n in names]
        bars = axis.bar([LABELS[n] for n in names], values, color=[COLORS[n] for n in names])
        axis.bar_label(bars, fmt="%.1f", padding=2)
        axis.set_title(title, color=NAVY, fontsize=10, fontweight="bold")
        axis.tick_params(axis="x", labelsize=8)
        axis.grid(axis="y", alpha=0.25)
        axis.margins(y=0.15)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def render(comparison, out_dir, ramp_start_s, initial_replicas):
    """Write latency_over_time.png and summary_bars.png; return their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    latency = out / "latency_over_time.png"
    bars = out / "summary_bars.png"
    _latency_over_time(comparison, latency, ramp_start_s, initial_replicas)
    _summary_bars(comparison, bars)
    return [latency, bars]
