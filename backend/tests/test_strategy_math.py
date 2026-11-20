"""Unit tests for the lap-time model and strategy search."""

import numpy as np

from app.services.strategy_math import (
    choose_pit_loss,
    compared_total,
    degradation_series,
    driver_pace_offset,
    empirical_pit_losses,
    estimate_fuel_per_lap,
    estimate_lap_time,
    find_optimal_strategies,
    fit_compound_models,
    fuel_penalty,
    lane_time_pit_loss,
    neutral_lap_numbers,
    pace_order_note,
    replay_residual,
    simulate_strategy,
    suggestion_is_legal,
    user_plan_problem,
    with_opening_tyre_age,
)


def _row(
    driver,
    lap,
    total,
    compound,
    life,
    stint,
    *,
    base,
    deg,
    fuel,
    offset=0.0,
    pit_in=False,
    pit_out=False,
    time=None,
    extra=0.0,
):
    remaining = total - lap
    if time is None and not pit_in and not pit_out:
        time = base[compound] + deg[compound] * life + fuel * remaining + offset + extra
    return {
        "driver": driver,
        "lap": lap,
        "time": time,
        "compound": compound,
        "tyre_life": life,
        "stint": stint,
        "pit_in": pit_in,
        "pit_out": pit_out,
        "pit_duration": None,
        "laps_remaining": remaining,
    }


def _race(total=40, fuel=0.04, noise=0.0):
    """Two drivers, soft-hard-soft, with a known tire and fuel model."""
    base = {"SOFT": 90.0, "HARD": 91.2}
    deg = {"SOFT": 0.06, "HARD": 0.03}
    offsets = {"AAA": 0.0, "BBB": 0.8}
    rows = []
    rng = np.random.default_rng(0)
    plan = [("SOFT", 1, 12, 1), ("HARD", 13, 26, 2), ("SOFT", 27, total, 3)]
    for driver, offset in offsets.items():
        for compound, start, end, stint in plan:
            for lap in range(start, end + 1):
                life = lap - start + 1
                pit_in = lap == end and stint < 3
                pit_out = lap == start and stint > 1
                extra = float(rng.normal(0, noise)) if noise else 0.0
                racing = base[compound] + deg[compound] * life + fuel * (total - lap) + offset
                time = None
                if pit_in:
                    time = racing + 18.0
                elif pit_out:
                    time = racing + 4.0
                row = _row(
                    driver, lap, total, compound, life, stint,
                    base=base, deg=deg, fuel=fuel, offset=offset,
                    pit_in=pit_in, pit_out=pit_out, time=time, extra=extra,
                )
                if time is None:
                    row["time"] = racing + extra
                rows.append(row)
    return rows, base, deg, fuel, total


def test_fuel_is_added_once_on_top_of_a_corrected_base():
    models = {"SOFT": {"base_time": 90.0, "deg_rate": 0.05}}
    # Tyre life 4, lap 10 of 50, fuel 0.04: corrected 90.2, fuel left is 40 laps.
    assert estimate_lap_time(models, "SOFT", 4, 10, 50, 0.04) == 90.2 + fuel_penalty(10, 50, 0.04)
    assert fuel_penalty(50, 50, 0.04) == 0


def test_fit_recovers_fuel_and_degradation_and_replay_is_close():
    rows, base, deg, fuel, total = _race()
    neutral = neutral_lap_numbers(rows)
    assert neutral == set()
    fitted_fuel, source = estimate_fuel_per_lap(rows, neutral)
    assert source == "estimated"
    assert abs(fitted_fuel - fuel) < 0.01

    models = fit_compound_models(rows, neutral, fitted_fuel)
    assert set(models) == {"SOFT", "HARD"}
    assert "MEDIUM" not in models
    # The field base sits between the two drivers (offsets 0 and 0.8).
    for compound in ("SOFT", "HARD"):
        assert abs(models[compound]["base_time"] - (base[compound] + 0.4)) < 0.2
        assert abs(models[compound]["deg_rate"] - deg[compound]) < 0.015
    assert models["SOFT"]["base_time"] < models["HARD"]["base_time"]

    offset_aaa = driver_pace_offset(rows, models, neutral, fitted_fuel, total, "AAA")
    offset = driver_pace_offset(rows, models, neutral, fitted_fuel, total, "BBB")
    assert abs(offset_aaa - (-0.4)) < 0.15
    assert abs(offset - 0.4) < 0.15

    losses = empirical_pit_losses(
        rows, models, neutral, fitted_fuel, total, {"AAA": offset_aaa, "BBB": offset}
    )
    # In-lap is +18s and out-lap is +4s versus a racing lap, so the stop costs 22s.
    assert abs(float(np.mean(losses["AAA"])) - 22.0) < 1.0

    stints = [
        {"compound": "SOFT", "laps": 12, "start_tyre_age": 0},
        {"compound": "HARD", "laps": 14, "start_tyre_age": 0},
        {"compound": "SOFT", "laps": 14, "start_tyre_age": 0},
    ]
    pit_loss, pit_source = choose_pit_loss(losses["AAA"], losses["AAA"], None)
    assert pit_source == "lap_delta"
    simulated = simulate_strategy(models, stints, pit_loss, total, fitted_fuel, offset_aaa, {})
    actual = {row["lap"]: row["time"] for row in rows if row["driver"] == "AAA" and row["time"] is not None}
    residual = replay_residual(simulated, actual)
    assert abs(residual["residual_seconds"]) < 3.0


def test_missing_lap_is_not_counted_on_either_side():
    rows, _, _, fuel, total = _race()
    rows[5]["time"] = None
    neutral = neutral_lap_numbers(rows)
    fitted_fuel, _ = estimate_fuel_per_lap(rows, neutral)
    models = fit_compound_models(rows, neutral, fitted_fuel)
    stints = [
        {"compound": "SOFT", "laps": 12},
        {"compound": "HARD", "laps": 14},
        {"compound": "SOFT", "laps": 14},
    ]
    simulated = simulate_strategy(models, stints, 22.0, total, fitted_fuel)
    actual = {
        row["lap"]: row["time"]
        for row in rows
        if row["driver"] == "AAA" and row["time"] is not None
    }
    assert 6 not in actual
    residual = replay_residual(simulated, actual)
    assert residual["timed_laps"] == total - 1
    # The missing lap's modelled ~90s is not part of the comparison.
    full = sum(lap["time_sec"] for lap in simulated)
    assert full - residual["replay_time"] > 80


def test_pit_loss_is_not_added_on_top_of_an_in_lap_that_already_contains_it():
    rows, _, _, fuel, total = _race()
    neutral = set()
    models = fit_compound_models(rows, neutral, fuel)
    offset = driver_pace_offset(rows, models, neutral, fuel, total, "AAA")
    losses = empirical_pit_losses(rows, models, neutral, fuel, total, {"AAA": offset})
    pit_loss = float(np.mean(losses["AAA"]))
    stints = [
        {"compound": "SOFT", "laps": 12},
        {"compound": "HARD", "laps": 14},
        {"compound": "SOFT", "laps": 14},
    ]
    simulated = simulate_strategy(models, stints, pit_loss, total, fuel, offset)
    pit_laps = [lap for lap in simulated if lap["is_pit_lap"]]
    assert len(pit_laps) == 2
    actual_by_lap = {row["lap"]: row for row in rows if row["driver"] == "AAA"}
    for modelled in pit_laps:
        actual_in = actual_by_lap[modelled["lap"]]
        actual_out = actual_by_lap[modelled["lap"] + 1]
        modelled_out = next(lap for lap in simulated if lap["lap"] == modelled["lap"] + 1)
        # The stop is charged once, across the in-lap and out-lap together.
        pair_gap = (modelled["time_sec"] + modelled_out["time_sec"]) - (actual_in["time"] + actual_out["time"])
        assert abs(pair_gap) < 1.5


def test_inconsistent_pit_durations_use_the_lane_time_only():
    # Stationary stops (~2.5s), one red-flag outlier, and real lane times.
    loss = lane_time_pit_loss([2.5, 2.4, 2.6, 24.0, 25.0, 23.0, 26.0, 2400.0])
    assert loss == 24.5
    assert lane_time_pit_loss([2.5, 2.5, 2.5, 3.0]) is None
    chosen, source = choose_pit_loss([], [], loss)
    assert source == "lane_time"
    assert chosen == 24.5


def test_missing_compound_is_not_invented_and_suggestions_stay_legal():
    rows, _, _, fuel, total = _race()
    models = fit_compound_models(rows, set(), fuel)
    assert "MEDIUM" not in models
    best = find_optimal_strategies(models, 22.0, total, fuel)
    assert best
    for stints in (plan for _, plan in best.values()):
        assert suggestion_is_legal(stints, ["SOFT", "HARD"], wet=False)
        compounds = [stint["compound"] for stint in stints]
        assert "MEDIUM" not in compounds
        assert len(set(compounds)) >= 2
        assert all(compounds[i] != compounds[i + 1] for i in range(len(compounds) - 1))
    message = user_plan_problem([{"compound": "MEDIUM", "laps": total}], ["SOFT", "HARD"], wet=False)
    assert message and "MEDIUM" in message


def test_implausible_pace_order_is_reported_and_not_rewritten():
    total = 36
    fuel = 0.04
    # Hard is genuinely faster in this sample. The model must say so.
    rows = []
    for driver, offset in (("AAA", 0.0), ("BBB", 0.4)):
        segments = [("HARD", 1, 18, 1, 89.0, 0.02), ("SOFT", 19, total, 2, 91.0, 0.08)]
        for compound, start, end, stint, base, deg in segments:
            for lap in range(start, end + 1):
                life = lap - start + 1
                pit_in = lap == end and stint == 1
                pit_out = lap == start and stint == 2
                racing = base + deg * life + fuel * (total - lap) + offset
                time = racing + (16 if pit_in else 3 if pit_out else 0)
                rows.append(
                    {
                        "driver": driver,
                        "lap": lap,
                        "time": time,
                        "compound": compound,
                        "tyre_life": life,
                        "stint": stint,
                        "pit_in": pit_in,
                        "pit_out": pit_out,
                        "pit_duration": None,
                        "laps_remaining": total - lap,
                    }
                )
        # A second hard stint would help fuel, but one long hard stint is enough
        # for the pace comparison. Add an earlier short hard run so fuel separates.
    # Give each driver two hard stints by rewriting nothing: add laps on a second race phase.
    extra = []
    for row in list(rows):
        if row["compound"] != "HARD":
            continue
    for driver, offset in (("AAA", 0.0), ("BBB", 0.4)):
        for lap in range(1, 9):
            extra.append(
                {
                    "driver": driver + "2",
                    "lap": lap,
                    "time": 89.0 + 0.02 * lap + fuel * (total - lap) + offset,
                    "compound": "HARD",
                    "tyre_life": lap,
                    "stint": 1,
                    "pit_in": False,
                    "pit_out": False,
                    "pit_duration": None,
                    "laps_remaining": total - lap,
                }
            )
            extra.append(
                {
                    "driver": driver + "2",
                    "lap": lap + 12,
                    "time": 89.0 + 0.02 * lap + fuel * (total - (lap + 12)) + offset,
                    "compound": "HARD",
                    "tyre_life": lap,
                    "stint": 2,
                    "pit_in": False,
                    "pit_out": False,
                    "pit_duration": None,
                    "laps_remaining": total - (lap + 12),
                }
            )
    rows.extend(extra)
    neutral = neutral_lap_numbers(rows)
    fitted_fuel, _ = estimate_fuel_per_lap(rows, neutral)
    models = fit_compound_models(rows, neutral, fitted_fuel)
    assert models["HARD"]["base_time"] < models["SOFT"]["base_time"]
    note = pace_order_note(models)
    assert "does not follow" in note
    assert "HARD" in models and models["HARD"]["observed"] is True


def test_chart_series_is_fuel_corrected():
    rows, _, _, fuel, _ = _race()
    models = fit_compound_models(rows, set(), fuel)
    series = degradation_series(rows, models, set(), fuel)
    raw = [row["time"] for row in rows if row["compound"] == "SOFT" and row["tyre_life"] == 3 and not row["pit_in"] and not row["pit_out"]]
    corrected = [
        row["time"] - fuel * row["laps_remaining"]
        for row in rows
        if row["compound"] == "SOFT" and row["tyre_life"] == 3 and not row["pit_in"] and not row["pit_out"]
    ]
    index = series["SOFT"]["tyre_life"].index(3)
    assert abs(series["SOFT"]["avg_lap_time"][index] - float(np.mean(corrected))) < 1e-6
    assert abs(float(np.mean(raw)) - float(np.mean(corrected))) > 0.5


def test_safety_car_lap_is_passed_through_and_a_wet_compound_is_modelled():
    rows, _, _, fuel, total = _race()
    for row in rows:
        if row["lap"] == 20:
            row["time"] = 130.0
    neutral = neutral_lap_numbers(rows)
    assert 20 in neutral

    wet_rows = []
    for lap in range(1, 31):
        for driver, stint, compound, base in (
            ("AAA", 1 if lap < 16 else 2, "INTERMEDIATE" if lap < 16 else "MEDIUM", 100.0 if lap < 16 else 92.0),
            ("BBB", 1 if lap < 16 else 2, "INTERMEDIATE" if lap < 16 else "MEDIUM", 100.0 if lap < 16 else 92.0),
        ):
            life = lap if lap < 16 else lap - 15
            wet_rows.append(
                {
                    "driver": driver,
                    "lap": lap,
                    "time": base + 0.05 * life + fuel * (30 - lap) + (0.3 if driver == "BBB" else 0),
                    "compound": compound,
                    "tyre_life": life,
                    "stint": stint,
                    "pit_in": lap == 15,
                    "pit_out": lap == 16,
                    "pit_duration": None,
                    "laps_remaining": 30 - lap,
                }
            )
    from app.services.strategy_math import is_wet_race

    assert is_wet_race(wet_rows, rainfall=True)
    models = fit_compound_models(wet_rows, set(), fuel)
    assert "INTERMEDIATE" in models
    assert "SOFT" not in models
    best = find_optimal_strategies(models, 20.0, 30, fuel, wet=True)
    for _, stints in best.values():
        assert suggestion_is_legal(stints, list(models), wet=True)
        assert all(stint["compound"] in {"INTERMEDIATE", "MEDIUM"} for stint in stints)


def test_red_flag_lap_flagged_as_pit_out_is_still_neutral():
    rows, _, _, _, total = _race()
    for row in rows:
        if row["lap"] == 8:
            row["pit_out"] = True
            row["time"] = 160.0
    neutral = neutral_lap_numbers(rows)
    assert 8 in neutral


def test_mixed_race_rejects_a_dry_compound_before_the_track_dried():
    from app.services.strategy_math import stint_fits_usage, stint_respects_length

    usage = {
        "INTERMEDIATE": set(range(1, 21)),
        "MEDIUM": set(range(18, 41)),
    }
    too_early = [
        {"compound": "MEDIUM", "laps": 20},
        {"compound": "INTERMEDIATE", "laps": 20},
    ]
    fits = [
        {"compound": "INTERMEDIATE", "laps": 18},
        {"compound": "MEDIUM", "laps": 22},
    ]
    assert stint_fits_usage(too_early, usage) is False
    assert stint_fits_usage(fits, usage) is True
    assert stint_respects_length(fits, {"INTERMEDIATE": 20, "MEDIUM": 22}) is True
    assert stint_respects_length(
        [{"compound": "MEDIUM", "laps": 47}, {"compound": "HARD", "laps": 5}],
        {"MEDIUM": 15, "HARD": 14},
    ) is False


def test_tiny_pace_inversion_is_not_called_out():
    models = {
        "SOFT": {"base_time": 90.05, "deg_rate": 0.0},
        "HARD": {"base_time": 90.0, "deg_rate": 0.0},
    }
    assert pace_order_note(models) == ""
    models["HARD"]["base_time"] = 89.0
    assert "does not follow" in pace_order_note(models)


def test_compared_total_ignores_laps_without_a_recorded_time():
    simulated = [
        {"lap": 1, "time_sec": 90.0},
        {"lap": 2, "time_sec": 91.0},
        {"lap": 3, "time_sec": 92.0},
    ]
    assert compared_total(simulated, {1: 90.0, 3: 92.5}) == 182.0


def test_pit_loss_is_added_on_the_out_lap():
    models = {
        "SOFT": {"base_time": 90.0, "deg_rate": 0.0},
        "HARD": {"base_time": 91.0, "deg_rate": 0.0},
    }
    stints = [{"compound": "SOFT", "laps": 4}, {"compound": "HARD", "laps": 4}]
    simulated = simulate_strategy(models, stints, 20.0, 8, 0.0)
    in_lap = simulated[3]
    out_lap = simulated[4]
    assert in_lap["is_pit_lap"] is True
    assert abs(in_lap["time_sec"] - estimate_lap_time(models, "SOFT", 4, 4, 8, 0.0)) < 1e-6
    assert abs(out_lap["time_sec"] - (estimate_lap_time(models, "HARD", 1, 5, 8, 0.0) + 20.0)) < 1e-6


def test_opening_tyre_age_applies_only_to_the_starting_compound():
    stints = [{"compound": "SOFT", "laps": 10}, {"compound": "HARD", "laps": 10}]
    aged = with_opening_tyre_age(stints, "SOFT", 3)
    assert aged[0]["start_tyre_age"] == 3
    assert "start_tyre_age" not in aged[1]
    fresh = with_opening_tyre_age(stints, "MEDIUM", 3)
    assert fresh[0].get("start_tyre_age") is None
    explicit = with_opening_tyre_age(
        [{"compound": "SOFT", "laps": 10, "start_tyre_age": 0}, {"compound": "HARD", "laps": 10}],
        "SOFT",
        3,
    )
    assert explicit[0]["start_tyre_age"] == 0
