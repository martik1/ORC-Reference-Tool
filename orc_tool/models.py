from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Optional


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    """Linearly interpolate ys(xs) at x, clamping outside the known range."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_left(xs, x)
    if xs[i] == x:
        return ys[i]
    x0, x1 = xs[i - 1], xs[i]
    y0, y1 = ys[i - 1], ys[i]
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


@dataclass
class PolarTable:
    """Wraps a certificate's `Allowances` block: seconds/mile allowance as a
    function of true wind speed (TWS, knots) and true wind angle (TWA, degrees)."""

    wind_speeds: list[float]
    wind_angles: list[float]
    r: dict[float, list[float]]  # benchmark TWA -> seconds/mile per wind_speeds entry
    beat: list[float]
    run: list[float]
    beat_angle: list[float]
    gybe_angle: list[float]
    extra: dict[str, list[float]]  # DW150/165/180, WL, CR, OC, ... per wind_speeds entry

    @classmethod
    def from_json(cls, allowances: dict) -> "PolarTable":
        wind_speeds = list(allowances["WindSpeeds"])
        wind_angles = list(allowances["WindAngles"])
        r = {twa: allowances[f"R{int(twa)}"] for twa in wind_angles}
        known = {"WindSpeeds", "WindAngles", "Beat", "Run", "BeatAngle", "GybeAngle"}
        known |= {f"R{int(twa)}" for twa in wind_angles}
        extra = {k: v for k, v in allowances.items() if k not in known}
        return cls(
            wind_speeds=wind_speeds,
            wind_angles=wind_angles,
            r=r,
            beat=list(allowances["Beat"]),
            run=list(allowances["Run"]),
            beat_angle=list(allowances["BeatAngle"]),
            gybe_angle=list(allowances["GybeAngle"]),
            extra=extra,
        )

    def _at_tws(self, tws: float, series: list[float]) -> float:
        return _interp(tws, self.wind_speeds, series)

    def seconds_per_mile(self, tws: float, twa: float) -> float:
        """Seconds/mile allowance at a given TWS (kt) and TWA (0-180 deg)."""
        twa = abs(twa) % 360
        if twa > 180:
            twa = 360 - twa

        beat_angle = self._at_tws(tws, self.beat_angle)
        gybe_angle = self._at_tws(tws, self.gybe_angle)
        beat = self._at_tws(tws, self.beat)
        run = self._at_tws(tws, self.run)

        if twa <= beat_angle:
            return beat
        if twa >= gybe_angle:
            return run

        mid_angles = [a for a in self.wind_angles if beat_angle < a < gybe_angle]
        angles = [beat_angle] + mid_angles + [gybe_angle]
        values = [beat] + [self._at_tws(tws, self.r[a]) for a in mid_angles] + [run]
        return _interp(twa, angles, values)

    def speed_knots(self, tws: float, twa: float) -> float:
        return 3600.0 / self.seconds_per_mile(tws, twa)

    def allowance_field(self, tws: float, fieldname: str) -> float:
        """Seconds/mile for a named wind-speed-dependent scoring field (e.g. WL/CR/OC)."""
        if fieldname not in self.extra:
            raise KeyError(
                f"Unknown wind-speed-dependent field {fieldname!r}; "
                f"available: {sorted(self.extra)}"
            )
        return self._at_tws(tws, self.extra[fieldname])

    def optimum_upwind(self, tws: float) -> tuple[float, float]:
        """Returns (beat angle deg, VMG speed kt) at a given TWS."""
        angle = self._at_tws(tws, self.beat_angle)
        speed = 3600.0 / self._at_tws(tws, self.beat)
        return angle, speed

    def optimum_downwind(self, tws: float) -> tuple[float, float]:
        """Returns (gybe/run angle deg, VMG speed kt) at a given TWS."""
        angle = self._at_tws(tws, self.gybe_angle)
        speed = 3600.0 / self._at_tws(tws, self.run)
        return angle, speed

    @property
    def tws_range(self) -> tuple[float, float]:
        return self.wind_speeds[0], self.wind_speeds[-1]


@dataclass
class Boat:
    ref_no: Optional[str]
    sail_no: Optional[str]
    name: str
    yacht_class: Optional[str]
    nat_auth: Optional[str]
    family: str
    country: Optional[str]
    raw: dict = field(repr=False)
    polar: PolarTable = field(repr=False)

    @classmethod
    def from_json(cls, rec: dict, country: Optional[str] = None) -> "Boat":
        return cls(
            ref_no=rec.get("RefNo"),
            sail_no=rec.get("SailNo"),
            name=rec.get("YachtName") or "(unnamed)",
            yacht_class=rec.get("Class"),
            nat_auth=rec.get("NatAuth"),
            family=rec.get("Family", "ORC"),
            country=country or rec.get("NatAuth"),
            raw=rec,
            polar=PolarTable.from_json(rec["Allowances"]),
        )

    def field(self, name: str):
        return self.raw.get(name)

    def __str__(self) -> str:
        cls = f" - {self.yacht_class}" if self.yacht_class else ""
        return f"{self.name} ({self.sail_no}){cls}"
