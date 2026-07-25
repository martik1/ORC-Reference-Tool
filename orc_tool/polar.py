from __future__ import annotations

import math
from typing import Optional

from orc_tool.models import Boat


def sample_polar(boat: Boat, tws: float, step_deg: float = 2.0) -> tuple[list[float], list[float]]:
    """Returns (angles_deg, speeds_kt) from the boat's beat angle to its run angle."""
    beat_angle, _ = boat.polar.optimum_upwind(tws)
    gybe_angle, _ = boat.polar.optimum_downwind(tws)
    angles = []
    a = beat_angle
    while a < gybe_angle:
        angles.append(a)
        a += step_deg
    angles.append(gybe_angle)
    speeds = [boat.polar.speed_knots(tws, a) for a in angles]
    return angles, speeds


def plot_polar(boats: list[Boat], tws: float, highlight: Optional[Boat] = None, show: bool = True):
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_thetamin(0)
    ax.set_thetamax(180)

    max_speed = 0.0
    for boat in boats:
        angles, speeds = sample_polar(boat, tws)
        theta = [math.radians(a) for a in angles]
        is_hl = highlight is not None and boat is highlight
        ax.plot(
            theta,
            speeds,
            label=str(boat),
            linewidth=2.8 if is_hl else 1.6,
            zorder=3 if is_hl else 2,
        )
        max_speed = max(max_speed, max(speeds))

    ax.set_rlabel_position(90)
    ax.set_ylim(0, max_speed * 1.1)
    ax.set_title(f"ORC polar diagram @ {tws:g} kt TWS", pad=20)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.15, -0.15), fontsize=8)
    fig.tight_layout()
    if show:
        plt.show()
    return fig
