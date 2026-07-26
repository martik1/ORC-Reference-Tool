"""Visualize race courses: inshore leg geometry (with wind and TWA per leg)
and offshore mark-by-mark distance profiles."""

from __future__ import annotations

import math
from typing import Optional

from orc_tool.course import CourseLeg, leg_twa


def _leg_vertices(legs: list[CourseLeg]) -> list[tuple[float, float]]:
    """Cumulative (x, y) NM positions, compass bearings (0=N, clockwise), start at origin."""
    x, y = 0.0, 0.0
    points = [(x, y)]
    for leg in legs:
        rad = math.radians(leg.bearing_deg)
        x += leg.distance_nm * math.sin(rad)
        y += leg.distance_nm * math.cos(rad)
        points.append((x, y))
    return points


def plot_inshore_course(
    legs: list[CourseLeg],
    title: Optional[str] = None,
    show: bool = True,
    save_path: Optional[str] = None,
):
    """Top-down course diagram: leg-by-leg track with mark numbers, cumulative
    distance, and a wind arrow + TWA annotation on each leg."""
    import matplotlib.pyplot as plt

    points = _leg_vertices(legs)
    xs, ys = zip(*points)

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot(xs, ys, "-", color="tab:blue", linewidth=1.2, zorder=2)

    # Marks are frequently revisited (a Windward/Leeward course is the same
    # two points back and forth) or very close together (a gate), so labels
    # are staggered around a ring rather than all placed at a fixed offset.
    offsets = [(10, 10), (10, -14), (-45, 10), (-45, -14), (10, 26), (-45, 26)]

    def _label(text: str, x: float, y: float, i: int, **kwargs):
        ox, oy = offsets[i % len(offsets)]
        ax.annotate(text, (x, y), textcoords="offset points", xytext=(ox, oy), fontsize=8, **kwargs)

    def _cluster_key(pt: tuple[float, float]) -> tuple[float, float]:
        return (round(pt[0], 3), round(pt[1], 3))

    if _cluster_key(points[0]) == _cluster_key(points[-1]):
        ax.plot(xs[0], ys[0], "s", color="green", markersize=10, zorder=3)
        _label("Start/Finish", xs[0], ys[0], 0, fontweight="bold")
    else:
        ax.plot(xs[0], ys[0], "s", color="green", markersize=10, zorder=3)
        _label("Start", xs[0], ys[0], 0, fontweight="bold")
        ax.plot(xs[-1], ys[-1], "s", color="red", markersize=10, zorder=3)
        _label("Finish", xs[-1], ys[-1], 1, fontweight="bold")

    # Out-and-back legs (e.g. a plain Windward/Leeward course) revisit the
    # same physical point and land on the same leg midpoint repeatedly --
    # group those into one combined label instead of stacking duplicates.
    mark_clusters: dict[tuple[float, float], list[str]] = {}
    cum = 0.0
    for i in range(1, len(legs)):
        cum += legs[i - 1].distance_nm
        mark_clusters.setdefault(_cluster_key(points[i]), []).append(f"M{i} ({cum:g} NM)")

    mid_clusters: dict[tuple[float, float], list[str]] = {}
    mid_points: dict[tuple[float, float], tuple[float, float]] = {}
    for i, leg in enumerate(legs):
        mid = ((points[i][0] + points[i + 1][0]) / 2, (points[i][1] + points[i + 1][1]) / 2)
        twa = leg_twa(leg.bearing_deg, leg.wind_from_deg)
        key = _cluster_key(mid)
        mid_points[key] = mid
        mid_clusters.setdefault(key, []).append(f"{leg.distance_nm:g} NM, brg {leg.bearing_deg:g}°, TWA {twa:.0f}°")

        wind_rad = math.radians(leg.wind_from_deg + 180)  # arrow points where the wind blows TO
        arrow_len = min(leg.distance_nm, max(0.15, leg.distance_nm * 0.2))
        ax.annotate(
            "",
            xy=(mid[0] + arrow_len * math.sin(wind_rad), mid[1] + arrow_len * math.cos(wind_rad)),
            xytext=mid,
            arrowprops=dict(arrowstyle="->", color="tab:orange", lw=1.5),
            zorder=4,
        )

    for cluster_i, (key, labels) in enumerate(mark_clusters.items()):
        mx, my = key
        ax.plot(mx, my, "o", color="tab:blue", markersize=6, zorder=3)
        _label(" / ".join(labels), mx, my, cluster_i + 2, fontweight="bold")

    for cluster_i, (key, labels) in enumerate(mid_clusters.items()):
        mx, my = mid_points[key]
        _label("\n".join(labels), mx, my, cluster_i, color="dimgray")

    ax.set_xlabel("NM (East +)")
    ax.set_ylabel("NM (North +)")
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.5)
    total_distance = sum(leg.distance_nm for leg in legs)
    ax.set_title(title or f"Inshore course: {len(legs)} legs, {total_distance:g} NM (orange arrows = wind direction)")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path)
    if show:
        plt.show()
    return fig


def plot_offshore_course(
    marks: list[dict],
    title: Optional[str] = None,
    show: bool = True,
    save_path: Optional[str] = None,
):
    """Mark-by-mark distance profile for an offshore course (no bearings
    available -- marks only carry cumulative distance from the start)."""
    import matplotlib.pyplot as plt

    distances = [0.0] + [m["distance_nm"] for m in marks]
    names = ["Start"] + [m["name"] for m in marks]

    fig, ax = plt.subplots(figsize=(max(6, len(marks) * 1.5), 2.5))
    ax.plot(distances, [0] * len(distances), "-o", color="tab:blue", zorder=2)

    for dist, name in zip(distances, names):
        ax.annotate(
            f"{name}\n{dist:g} NM",
            (dist, 0),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            fontsize=9,
        )

    ax.set_yticks([])
    ax.set_xlabel("Cumulative distance from start (NM)")
    ax.set_ylim(-1, 1)
    ax.spines[["top", "left", "right"]].set_visible(False)
    ax.set_title(title or f"Offshore course: {len(marks)} marks, {distances[-1]:g} NM total")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path)
    if show:
        plt.show()
    return fig
