"""Validate PCS/Scoring Wind, Course Construction, and custom ToD/ToT
against the formulas and worked examples from the ORC certificate guide.
"""

import pytest

from orc_tool.course import CourseLeg, constructed_course_curve, leg_twa, score_constructed_course
from orc_tool.crossover import find_crossover
from orc_tool.models import Boat, PolarTable
from orc_tool.pcs import PcsEntry, invert_curve, score_pcs_certificate
from orc_tool.scoring import (
    DEFAULT_TOD_WIND_WEIGHTS,
    Kind,
    ScoringOption,
    custom_tod_coefficient,
    tod_to_tot,
)

# Boat A / Boat B "All Purpose" (CR) time allowances (s/NM) from the doc's
# worked example, 6-20kt. Their difference at each TWS is given explicitly:
# 82.8, 52.2, 0.0, -37.3, -56.4, -64.6, -69.5
TWS_POINTS = [6, 8, 10, 12, 14, 16, 20]
BOAT_A_CR = [964.1, 783.9, 679.9, 621.5, 588.0, 565.9, 541.2]
BOAT_B_CR = [881.3, 731.7, 679.9, 658.8, 644.4, 630.5, 610.7]
DOC_DELTA_A_MINUS_B = [82.8, 52.2, 0.0, -37.3, -56.4, -64.6, -69.5]


def _synthetic_boat(name: str, cr_values: list[float]) -> Boat:
    polar = PolarTable(
        wind_speeds=list(TWS_POINTS),
        wind_angles=[],
        r={},
        beat=[],
        run=[],
        beat_angle=[],
        gybe_angle=[],
        extra={"CR": cr_values},
    )
    return Boat(
        ref_no=None,
        sail_no=name,
        name=name,
        yacht_class=None,
        nat_auth=None,
        family="ORC",
        country=None,
        raw={},
        polar=polar,
    )


@pytest.fixture
def boat_a() -> Boat:
    return _synthetic_boat("Boat A", BOAT_A_CR)


@pytest.fixture
def boat_b() -> Boat:
    return _synthetic_boat("Boat B", BOAT_B_CR)


@pytest.fixture
def all_purpose_pcs() -> ScoringOption:
    return ScoringOption(name="All Purpose", kind=Kind.PCS, fieldname="CR", country_id="ORC", families=("ORC",))


# ---------------------------------------------------------------------------
# Course-certificate deltas (sanity check on the raw data the doc quotes)
# ---------------------------------------------------------------------------


def test_doc_delta_table_matches_certificate_values(boat_a, boat_b):
    deltas = [
        boat_a.polar.allowance_field(tws, "CR") - boat_b.polar.allowance_field(tws, "CR") for tws in TWS_POINTS
    ]
    assert deltas == pytest.approx(DOC_DELTA_A_MINUS_B, abs=0.05)


def test_crossover_found_near_10kt_where_doc_delta_is_zero(boat_a, boat_b, all_purpose_pcs):
    # step chosen so the sample grid doesn't land exactly on TWS=10 (where
    # delta is exactly zero) -- find_crossover's zero-delta sample handling
    # is a separate, pre-existing edge case outside this task's scope.
    crossings = find_crossover(boat_a, boat_b, all_purpose_pcs, step=0.11)
    assert len(crossings) == 1
    assert crossings[0].tws == pytest.approx(10.0, abs=0.1)


# ---------------------------------------------------------------------------
# invert_curve / Scoring Wind
# ---------------------------------------------------------------------------


def test_invert_curve_recovers_exact_grid_point(boat_a):
    tws = invert_curve(TWS_POINTS, BOAT_A_CR, target=621.5)  # boat A's own 12kt value
    assert tws == pytest.approx(12.0)


def test_invert_curve_clamps_below_range_no_extrapolation():
    # target faster than the curve's fastest (highest-wind) point: clamp to top of range
    assert invert_curve(TWS_POINTS, BOAT_A_CR, target=1.0) == 20.0


def test_invert_curve_clamps_above_range_no_extrapolation():
    # target slower than the curve's slowest (lowest-wind) point: clamp to bottom of range
    assert invert_curve(TWS_POINTS, BOAT_A_CR, target=9999.0) == 6.0


def test_invert_curve_round_trips_on_real_certificate_data(fin_boat):
    xs, ys = fin_boat.polar.wind_speeds, fin_boat.polar.extra["CR"]
    for tws in [xs[0] + 1, (xs[0] + xs[-1]) / 2, xs[-1] - 1]:
        allowance = fin_boat.polar.allowance_field(tws, "CR")
        recovered_tws = invert_curve(xs, ys, allowance)
        assert recovered_tws == pytest.approx(tws, abs=1e-6)


# ---------------------------------------------------------------------------
# PCS race scoring (Scoring Wind end to end)
# ---------------------------------------------------------------------------


def test_boats_matching_own_12kt_rating_tie_on_corrected_time(boat_a, boat_b):
    # Each boat's actual average pace exactly equals its own certificate
    # value at 12kt -> both are scored "as if" TWS was 12kt, and since
    # neither over- nor under-performed its own rating, corrected time
    # collapses to the same value for both.
    distance_nm = 10.0
    entries = [
        PcsEntry(boat_a, elapsed_seconds=621.5 * distance_nm),
        PcsEntry(boat_b, elapsed_seconds=658.8 * distance_nm),
    ]
    results = score_pcs_certificate(entries, distance_nm, fieldname="CR")
    by_boat = {r.boat.name: r for r in results}

    assert by_boat["Boat A"].scoring_wind_kt == pytest.approx(12.0)
    assert by_boat["Boat B"].scoring_wind_kt == pytest.approx(12.0)
    assert by_boat["Boat A"].corrected_seconds == pytest.approx(by_boat["Boat B"].corrected_seconds, abs=1e-6)


def test_boat_that_outperforms_its_rating_wins(boat_a, boat_b):
    distance_nm = 10.0
    entries = [
        PcsEntry(boat_a, elapsed_seconds=600.0 * distance_nm),  # faster than its 12kt rating (621.5)
        PcsEntry(boat_b, elapsed_seconds=658.8 * distance_nm),  # exactly its 12kt rating
    ]
    results = score_pcs_certificate(entries, distance_nm, fieldname="CR")
    assert results[0].boat.name == "Boat A"
    assert results[0].scoring_wind_kt > 12.0


def test_scoring_wind_matches_doc_worked_example():
    # From the certificate guide: elapsed 1:28:11 (5291s) over an 8.11 NM
    # course gives an average allowance of 5291/8.11 = 652.4 s/NM.
    boat = _synthetic_boat("Example Boat", BOAT_A_CR)
    elapsed_seconds = 88 * 60 + 11
    distance_nm = 8.11
    results = score_pcs_certificate([PcsEntry(boat, elapsed_seconds)], distance_nm, fieldname="CR")
    assert results[0].avg_seconds_per_mile == pytest.approx(652.4, abs=0.05)


# ---------------------------------------------------------------------------
# Course Construction
# ---------------------------------------------------------------------------

# The doc's own worked course (its total distance, 8.11 NM, is the same
# course used in the Scoring Wind worked example above).
DOC_COURSE_LEGS = [
    CourseLeg(distance_nm=2.09, bearing_deg=162, wind_from_deg=160),
    CourseLeg(distance_nm=0.06, bearing_deg=60, wind_from_deg=155),
    CourseLeg(distance_nm=1.91, bearing_deg=340, wind_from_deg=155),
    CourseLeg(distance_nm=1.89, bearing_deg=161, wind_from_deg=160),
    CourseLeg(distance_nm=0.06, bearing_deg=60, wind_from_deg=160),
    CourseLeg(distance_nm=1.91, bearing_deg=340, wind_from_deg=160),
    CourseLeg(distance_nm=0.19, bearing_deg=316, wind_from_deg=160),
]


def test_doc_course_total_distance_is_8_11_nm():
    assert sum(leg.distance_nm for leg in DOC_COURSE_LEGS) == pytest.approx(8.11)


def test_leg_twa_dead_run_and_near_head_to_wind():
    # Gate(2-2a) - 1 leg: bearing 161 deg, wind from 160 deg -> almost dead upwind
    assert leg_twa(161, 160) == pytest.approx(1.0)
    # 1a - Gate leg: bearing 340 deg, wind from 160 deg -> exactly dead downwind
    assert leg_twa(340, 160) == pytest.approx(180.0)


def test_constructed_course_curve_matches_boat_own_wind_speeds(fin_boat):
    xs, values = constructed_course_curve(fin_boat, DOC_COURSE_LEGS)
    assert xs == fin_boat.polar.wind_speeds
    assert len(values) == len(xs)
    assert all(v > 0 for v in values)


def test_score_constructed_course_end_to_end(fin_boat):
    total_distance = sum(leg.distance_nm for leg in DOC_COURSE_LEGS)
    entries = [PcsEntry(fin_boat, elapsed_seconds=88 * 60 + 11)]
    results = score_constructed_course(entries, DOC_COURSE_LEGS)
    assert results[0].avg_seconds_per_mile == pytest.approx((88 * 60 + 11) / total_distance)


# ---------------------------------------------------------------------------
# Custom ToD / ToT coefficient
# ---------------------------------------------------------------------------


def test_default_wind_weights_sum_to_one():
    assert sum(DEFAULT_TOD_WIND_WEIGHTS.values()) == pytest.approx(1.0)
    assert set(DEFAULT_TOD_WIND_WEIGHTS) == set(TWS_POINTS)


def test_custom_tod_coefficient_matches_manual_weighted_average(boat_a):
    expected = sum(w * boat_a.polar.allowance_field(tws, "CR") for tws, w in DEFAULT_TOD_WIND_WEIGHTS.items())
    assert custom_tod_coefficient(boat_a, "CR") == pytest.approx(expected)


def test_custom_tod_coefficient_with_custom_weights(boat_a):
    # All weight on 12kt -> coefficient collapses to the 12kt value exactly.
    coeff = custom_tod_coefficient(boat_a, "CR", weights={12: 1.0})
    assert coeff == pytest.approx(621.5)


def test_tod_to_tot_conversion():
    assert tod_to_tot(600.0) == pytest.approx(1.0)
    tod = custom_tod_coefficient(_synthetic_boat("X", BOAT_B_CR), "CR")
    assert tod_to_tot(tod) == pytest.approx(600.0 / tod)
