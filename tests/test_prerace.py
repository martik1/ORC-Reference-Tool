"""Validate the pre-race inshore (constructed course) and offshore
(published Weather Routing rating) delta calculations."""

import pytest

from orc_tool.course import CourseLeg, constructed_course_curve
from orc_tool.models import _interp
from orc_tool.prerace import KNOTS_PER_MS, inshore_deltas, offshore_deltas, to_knots

LEGS = [
    CourseLeg(distance_nm=1.0, bearing_deg=20, wind_from_deg=200),
    CourseLeg(distance_nm=1.0, bearing_deg=200, wind_from_deg=200),
]


def test_to_knots_passthrough_and_conversion():
    assert to_knots(12.0, "kt") == 12.0
    assert to_knots(1.0, "m/s") == pytest.approx(KNOTS_PER_MS)


def test_to_knots_rejects_unknown_unit():
    with pytest.raises(ValueError):
        to_knots(12.0, "mph")


def test_reference_boat_has_zero_delta(fin_boat, fin_boat_2):
    rows = inshore_deltas([fin_boat, fin_boat_2], fin_boat, LEGS, tws_kt=12.0)
    ref_row = next(r for r in rows if r.boat is fin_boat)
    assert ref_row.delta_seconds == 0.0


def test_inshore_delta_matches_manual_rating_difference(fin_boat, fin_boat_2):
    rows = inshore_deltas([fin_boat, fin_boat_2], fin_boat, LEGS, tws_kt=12.0)
    by_boat = {id(r.boat): r for r in rows}

    total_distance = sum(leg.distance_nm for leg in LEGS)
    xs_ref, ys_ref = constructed_course_curve(fin_boat, LEGS)
    xs_2, ys_2 = constructed_course_curve(fin_boat_2, LEGS)
    expected_delta = (_interp(12.0, xs_2, ys_2) - _interp(12.0, xs_ref, ys_ref)) * total_distance

    assert by_boat[id(fin_boat_2)].delta_seconds == pytest.approx(expected_delta)


def test_offshore_delta_scales_linearly_with_distance(fin_boat, fin_boat_2):
    wr_ratings = {fin_boat.sail_no: 550.0, fin_boat_2.sail_no: 560.0}
    marks = [{"name": "M1", "distance_nm": 10.0}, {"name": "M2", "distance_nm": 20.0}]
    rows = offshore_deltas([fin_boat, fin_boat_2], fin_boat, marks, wr_ratings)

    assert rows[0].deltas[fin_boat.sail_no] == 0.0
    assert rows[0].deltas[fin_boat_2.sail_no] == pytest.approx(10.0 * 10.0)  # (560-550)*10nm
    assert rows[1].deltas[fin_boat_2.sail_no] == pytest.approx(10.0 * 20.0)
    # doubling the distance should exactly double the delta
    assert rows[1].deltas[fin_boat_2.sail_no] == pytest.approx(2 * rows[0].deltas[fin_boat_2.sail_no])
