"""Deterministic matplotlib figures (Agg backend, fixed metadata)."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {"A1": "#3b6ea5", "A2": "#c8553d", "A3": "#8a9a5b"}
LABELS = {"A1": "A1 queue position", "A2": "A2 adverse selection", "A3": "A3 competition"}


def _panel(ax: Any, att: dict[str, Any], title: str) -> None:
    """One stacked bar per cancel policy; whiskers are bootstrap CIs of the total."""
    policies = [p for p in ("pessimistic", "uniform", "optimistic") if p in att]
    for x, pol in enumerate(policies):
        cis = att[pol]["attribution_bps"]
        pos = neg = 0.0
        for axis in ("A2", "A1", "A3"):
            ci = cis.get(axis)
            v = 0.0 if ci is None else float(ci["estimate"])
            base = pos if v >= 0 else neg
            ax.bar(
                x,
                v,
                bottom=base,
                color=COLORS[axis],
                width=0.6,
                label=LABELS[axis] if x == 0 else None,
                edgecolor="white",
                linewidth=0.5,
            )
            if v >= 0:
                pos += v
            else:
                neg += v
        total = cis.get("total")
        if total is not None:
            t = float(total["estimate"])
            ax.errorbar(
                x,
                t,
                yerr=[[t - float(total["low"])], [float(total["high"]) - t]],
                fmt="o",
                color="black",
                capsize=4,
                markersize=4,
            )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(range(len(policies)))
    ax.set_xticklabels([p if p != "uniform" else "uniform\n(headline)" for p in policies])
    ax.set_ylabel("AS shortfall vs PolicyClassOptimum, bps")
    ax.set_title(title, fontsize=10)


def attribution_figure(report: dict[str, Any], path: Path) -> Path:
    strategy = report["strategies"]["avellaneda_stoikov"]["by_cancel_policy"]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    title = "Where AS loses: Shapley attribution, dot = total with 95% CI"
    if report.get("fixture_output"):
        title += "\nFIXTURE OUTPUT: synthetic data, not a market result"
    _panel(ax, strategy, title)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=120, metadata={"Software": None, "CreationDate": None})
    plt.close(fig)
    return path
