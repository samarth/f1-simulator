"""Tire models and strategy simulation built from a loaded race."""

from __future__ import annotations

import pandas as pd

from .strategy_math import (
    ALL_COMPOUNDS,
    attach_field_deltas,
    choose_pit_loss,
    compared_total,
    degradation_series,
    driver_pace_offset,
    compound_usage,
    expand_usage,
    longest_observed_stint,
    empirical_pit_losses,
    estimate_fuel_per_lap,
    field_pace_by_lap,
    field_neutral_times,
    find_optimal_strategies,
    fit_compound_models,
    fuel_effect_payload,
    green_rmse,
    is_wet_race,
    lane_time_pit_loss,
    neutral_lap_numbers,
    pace_order_note,
    replay_residual,
    simulate_strategy,
    unmodeled_compounds,
    user_plan_problem,
)

# Re-exported for callers and tests that still import the simulator from here.
__all__ = [
    "build_degradation_model",
    "build_race_model",
    "driver_context",
    "get_race_degradation_data",
    "get_pit_stop_stats",
    "get_driver_actual_strategy",
    "get_weather_data",
    "get_fuel_effect_data",
    "simulate_strategy",
    "analyze_stints",
    "find_optimal_strategies",
    "replay_driver",
    "user_plan_problem",
]


def _rows(session) -> tuple[list[dict], int]:
    frame = session.laps
    if frame is None or frame.empty:
        return [], 0
    total = int(frame["LapNumber"].max())
    rows = []
    for record in frame.itertuples(index=False):
        lap_time = getattr(record, "LapTime", None)
        seconds = None
        if lap_time is not None and not pd.isna(lap_time):
            seconds = float(lap_time.total_seconds())
        pit_duration = getattr(record, "PitDuration", None)
        if pit_duration is not None and pd.isna(pit_duration):
            pit_duration = None
        lap = int(record.LapNumber)
        rows.append(
            {
                "driver": str(record.Driver),
                "lap": lap,
                "time": seconds,
                "compound": str(getattr(record, "Compound", "UNKNOWN")),
                "tyre_life": int(getattr(record, "TyreLife", 1) or 1),
                "stint": int(getattr(record, "Stint", 0) or 0),
                "pit_in": bool(getattr(record, "IsPitIn", False)),
                "pit_out": bool(getattr(record, "IsPitOut", False)),
                "pit_duration": None if pit_duration is None else float(pit_duration),
                "laps_remaining": max(total - lap, 0),
            }
        )
    return rows, total


def build_race_model(session, rainfall: bool | None = None) -> dict:
    """Field tire model, fuel effect, and a pit loss that does not depend on one driver."""
    rows, total_laps = _rows(session)
    if rainfall is None:
        weather = get_weather_data(session)
        rainfall = bool(weather.get("rainfall"))
    neutral = neutral_lap_numbers(rows)
    fuel_per_lap, fuel_source = estimate_fuel_per_lap(rows, neutral)
    models = fit_compound_models(rows, neutral, fuel_per_lap)
    wet = is_wet_race(rows, rainfall)
    mixed = wet and any(compound in ("SOFT", "MEDIUM", "HARD") for compound in models) and any(
        compound in ("INTERMEDIATE", "WET") for compound in models
    )
    field_pace = field_pace_by_lap(rows, neutral) if mixed else {}
    if mixed and field_pace:
        attach_field_deltas(models, rows, neutral, field_pace)
    durations = [row["pit_duration"] for row in rows if row["pit_duration"] is not None]
    # Offsets are not known yet. A first pass with zero offset still ranks stops;
    # driver_context recomputes the selected driver's loss with their offset.
    losses = empirical_pit_losses(rows, models, neutral, fuel_per_lap, total_laps, {}, field_pace or None)
    field_losses = [loss for values in losses.values() for loss in values]
    field_pit, pit_source = choose_pit_loss([], field_losses, lane_time_pit_loss(durations))
    return {
        "rows": rows,
        "total_laps": total_laps,
        "models": models,
        "fuel_per_lap": fuel_per_lap,
        "fuel_source": fuel_source,
        "neutral": neutral,
        "neutral_times": field_neutral_times(rows, neutral),
        "wet": wet,
        "observed": [compound for compound in ALL_COMPOUNDS if compound in models],
        "unmodeled": unmodeled_compounds(rows, models),
        "pace_note": pace_order_note(models),
        "pit_loss": field_pit,
        "pit_source": pit_source,
        "pit_losses_by_driver": losses,
        "lane_loss": lane_time_pit_loss(durations),
        "field_losses": field_losses,
        "windows": expand_usage(compound_usage(rows)),
        "max_stint": longest_observed_stint(rows),
        "mixed": mixed,
        "field_pace": field_pace,
    }


def driver_context(race_model: dict, driver: str) -> dict:
    """Pace offset and pit loss for one driver, plus the neutral times used in their replay."""
    rows = race_model["rows"]
    models = race_model["models"]
    total = race_model["total_laps"]
    fuel = race_model["fuel_per_lap"]
    neutral = race_model["neutral"]
    field_pace = race_model.get("field_pace") or None
    offset = driver_pace_offset(rows, models, neutral, fuel, total, driver, field_pace)
    losses = empirical_pit_losses(rows, models, neutral, fuel, total, {driver: offset}, field_pace)
    driver_losses = losses.get(driver, race_model["pit_losses_by_driver"].get(driver, []))
    pit_loss, pit_source = choose_pit_loss(driver_losses, race_model["field_losses"], race_model["lane_loss"])
    neutral_times = dict(race_model["neutral_times"])
    # A neutralized lap is the same whichever strategy you pick, including a lap
    # flagged as a pit out during a red flag. Use this driver's recorded time so a
    # suggestion cannot beat him by inventing a faster safety-car lap.
    for row in rows:
        if row["driver"] != driver or row["lap"] not in neutral or row["time"] is None:
            continue
        neutral_times[row["lap"]] = float(row["time"])
    rmse = green_rmse(rows, models, neutral, fuel, total, driver, offset, field_pace)
    return {
        "driver_offset": offset,
        "pit_loss": pit_loss,
        "pit_source": pit_source,
        "neutral_times": neutral_times,
        "green_rmse": rmse,
    }


def build_degradation_model(session) -> dict:
    return build_race_model(session)["models"]


def get_race_degradation_data(session, fuel_corrected: bool = True) -> dict:
    race_model = build_race_model(session)
    if not fuel_corrected:
        # Chart the raw times. The fuel flag used to be ignored; honor it.
        rows = []
        for row in race_model["rows"]:
            copied = dict(row)
            copied["laps_remaining"] = 0
            rows.append(copied)
        return degradation_series(rows, race_model["models"], race_model["neutral"], 0.0)
    return degradation_series(
        race_model["rows"],
        race_model["models"],
        race_model["neutral"],
        race_model["fuel_per_lap"],
    )


def get_fuel_effect_data(total_laps: int = 57, race_model: dict | None = None) -> dict:
    if race_model is None:
        return fuel_effect_payload(total_laps, 0.04, "standard")
    return fuel_effect_payload(total_laps, race_model["fuel_per_lap"], race_model["fuel_source"])


def get_pit_stop_stats(session) -> dict:
    race_model = build_race_model(session)
    losses = race_model["field_losses"]
    if losses:
        return {
            "avg_pit_time": float(race_model["pit_loss"]),
            "min_pit_time": float(min(losses)),
            "max_pit_time": float(max(losses)),
            "num_stops": len(losses),
            "source": race_model["pit_source"],
        }
    loss = race_model["pit_loss"]
    return {
        "avg_pit_time": loss,
        "min_pit_time": loss,
        "max_pit_time": loss,
        "num_stops": 0,
        "source": race_model["pit_source"],
    }


def get_weather_data(session) -> dict:
    """Extract weather conditions from the session."""
    weather = session.weather_data

    if weather is None or weather.empty:
        return {
            "available": False,
            "air_temp": None,
            "track_temp": None,
            "humidity": None,
            "rainfall": False,
            "wind_speed": None,
            "conditions": "Unknown",
        }

    air_temp = weather["AirTemp"].mean() if "AirTemp" in weather.columns else None
    track_temp = weather["TrackTemp"].mean() if "TrackTemp" in weather.columns else None
    humidity = weather["Humidity"].mean() if "Humidity" in weather.columns else None
    rainfall = bool(weather["Rainfall"].max() > 0) if "Rainfall" in weather.columns else False
    wind_speed = weather["WindSpeed"].mean() if "WindSpeed" in weather.columns else None

    if rainfall:
        conditions = "Wet"
    elif track_temp and track_temp > 40:
        conditions = "Hot"
    elif track_temp and track_temp < 20:
        conditions = "Cool"
    else:
        conditions = "Dry"

    def _round(value):
        if value is None or pd.isna(value):
            return None
        return round(float(value), 1)

    return {
        "available": True,
        "air_temp": _round(air_temp),
        "track_temp": _round(track_temp),
        "humidity": _round(humidity),
        "rainfall": rainfall,
        "wind_speed": _round(wind_speed),
        "conditions": conditions,
        "track_temp_min": _round(weather["TrackTemp"].min()) if "TrackTemp" in weather.columns else None,
        "track_temp_max": _round(weather["TrackTemp"].max()) if "TrackTemp" in weather.columns else None,
    }


def get_driver_actual_strategy(session, driver: str) -> dict | None:
    """What the driver did, including the tyre age the stint actually started on."""
    laps = session.laps
    driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
    if driver_laps.empty:
        return None

    stints = []
    current = None
    for _, lap in driver_laps.iterrows():
        stint_num = int(lap.get("Stint", 1) or 1)
        compound = str(lap.get("Compound", "UNKNOWN"))
        tyre_life = int(lap.get("TyreLife", 1) or 1)
        if current is None or current["stint"] != stint_num:
            if current is not None:
                stints.append(current)
            current = {
                "stint": stint_num,
                "compound": compound,
                "start_lap": int(lap["LapNumber"]),
                "end_lap": int(lap["LapNumber"]),
                "laps": 1,
                "start_tyre_age": max(tyre_life - 1, 0),
            }
        else:
            current["end_lap"] = int(lap["LapNumber"])
            current["laps"] += 1
    if current is not None:
        stints.append(current)

    lap_times = []
    for _, lap in driver_laps.iterrows():
        if pd.notna(lap["LapTime"]):
            lap_times.append(
                {
                    "lap": int(lap["LapNumber"]),
                    "time_sec": float(lap["LapTime"].total_seconds()),
                    "compound": str(lap.get("Compound", "UNKNOWN")),
                    "tyre_life": int(lap.get("TyreLife", 0) or 0),
                }
            )

    pit_laps = []
    for index in range(len(stints) - 1):
        pit_laps.append(
            {
                "lap": stints[index]["end_lap"],
                "from_compound": stints[index]["compound"],
                "to_compound": stints[index + 1]["compound"],
            }
        )

    return {
        "stints": stints,
        "lap_times": lap_times,
        "total_time": float(sum(lap["time_sec"] for lap in lap_times)),
        "pit_laps": pit_laps,
        "total_laps": int(driver_laps["LapNumber"].max()),
    }


def replay_driver(session, driver: str, actual: dict | None = None) -> dict | None:
    """Run the driver's own stints through the model and report the miss."""
    if actual is None:
        actual = get_driver_actual_strategy(session, driver)
    if actual is None:
        return None
    race_model = build_race_model(session)
    context = driver_context(race_model, driver)
    neutral_times = dict(context["neutral_times"])
    for lap in actual["lap_times"]:
        if lap["lap"] in race_model["neutral"]:
            neutral_times[lap["lap"]] = lap["time_sec"]
    stints = [
        {
            "compound": stint["compound"],
            "laps": stint["laps"],
            "start_tyre_age": stint.get("start_tyre_age", 0),
        }
        for stint in actual["stints"]
    ]
    simulated = simulate_strategy(
        race_model["models"],
        stints,
        context["pit_loss"],
        race_model["total_laps"],
        race_model["fuel_per_lap"],
        context["driver_offset"],
        neutral_times,
        race_model.get("field_pace") or None,
    )
    actual_by_lap = {lap["lap"]: lap["time_sec"] for lap in actual["lap_times"]}
    # Pit in/out laps are not green-flag racing laps. The replay keeps the
    # recorded time so a slow stop is not treated as a tire-model error.
    pit_laps = {
        row["lap"]
        for row in race_model["rows"]
        if row["driver"] == driver and (row["pit_in"] or row["pit_out"]) and row["time"] is not None
    }
    for lap in simulated:
        if lap["lap"] in pit_laps and lap["lap"] in actual_by_lap:
            lap["time_sec"] = actual_by_lap[lap["lap"]]
            lap["neutral"] = True
    residual = replay_residual(simulated, actual_by_lap)
    rmse = context["green_rmse"]
    residual["green_rmse"] = None if rmse is None else round(rmse, 3)
    residual["driver_offset"] = round(context["driver_offset"], 3)
    residual["pit_loss"] = round(context["pit_loss"], 3)
    residual["pit_source"] = context["pit_source"]
    note = (
        f"Replaying the real stints is {residual['residual_seconds']:+.1f}s "
        f"versus the recorded laps ({residual['residual_per_lap']:+.3f}s per lap)."
    )
    if rmse is not None:
        note += f" Green-lap scatter around the fit is {rmse:.2f}s RMSE."
    residual["note"] = note
    return residual


def analyze_stints(
    models: dict,
    user_stints: list[dict],
    actual: dict | None,
    pit_loss: float,
    total_race_laps: int,
    fuel_per_lap: float = 0.04,
    driver_offset: float = 0.0,
    neutral_times: dict | None = None,
    field_pace: dict | None = None,
) -> list[dict]:
    """Per-stint gap between the user's plan and what the driver recorded."""
    if not actual or not actual.get("lap_times"):
        return []
    simulated = simulate_strategy(
        models, user_stints, pit_loss, total_race_laps, fuel_per_lap, driver_offset, neutral_times, field_pace
    )
    actual_by_lap = {lap["lap"]: lap for lap in actual["lap_times"]}
    results = []
    cursor = 0
    for index, stint in enumerate(user_stints):
        count = int(stint["laps"])
        chunk = simulated[cursor : cursor + count]
        cursor += count
        if not chunk:
            continue
        start_lap = chunk[0]["lap"]
        end_lap = chunk[-1]["lap"]
        user_time = sum(lap["time_sec"] for lap in chunk)
        actual_time = 0.0
        actual_count = 0
        for lap in range(start_lap, end_lap + 1):
            if lap in actual_by_lap:
                actual_time += actual_by_lap[lap]["time_sec"]
                actual_count += 1
        if actual_count == 0:
            continue
        delta = user_time - actual_time
        results.append(
            {
                "stint": index + 1,
                "compound": stint["compound"],
                "laps": count,
                "delta": round(delta, 3),
                "explanation": _explain_stint(
                    models, stint["compound"], count, delta, actual, start_lap, end_lap, index, user_stints
                ),
            }
        )
    return results


def _explain_stint(
    models: dict,
    compound: str,
    num_laps: int,
    delta: float,
    actual: dict,
    start_lap: int,
    end_lap: int,
    stint_idx: int,
    user_stints: list[dict],
) -> str:
    abs_delta = abs(delta)
    model = models.get(compound, {})
    deg_rate = model.get("deg_rate", 0.04)
    late_deg = deg_rate * num_laps
    cliff = late_deg > 1.5

    actual_compounds = set()
    for lap in actual.get("lap_times", []):
        if start_lap <= lap["lap"] <= end_lap:
            actual_compounds.add(lap["compound"])

    actual_pits = [pit["lap"] for pit in actual.get("pit_laps", [])]
    pit_timing_diff = None
    if stint_idx < len(user_stints) - 1 and actual_pits:
        closest = min(actual_pits, key=lambda pit: abs(pit - end_lap))
        pit_timing_diff = end_lap - closest

    if abs_delta < 1.0:
        return "Similar pace to actual — well matched."
    if cliff and delta > 0:
        return f"Tire cliff: {compound} degrades {late_deg:.1f}s by lap {num_laps}. Consider pitting earlier."
    if pit_timing_diff is not None and abs(pit_timing_diff) > 5 and delta > 0:
        direction = "later" if pit_timing_diff > 0 else "earlier"
        length = "long" if pit_timing_diff > 0 else "short"
        return f"Pitted {abs(pit_timing_diff)} laps {direction} than actual — stint too {length} on {compound}."
    if len(actual_compounds) == 1 and compound not in actual_compounds:
        actual_compound = next(iter(actual_compounds))
        if delta > 0:
            return (
                f"Used {compound} where actual used {actual_compound} — lost {abs_delta:.1f}s. "
                f"{actual_compound} may suit this phase better."
            )
        return (
            f"Used {compound} where actual used {actual_compound} — gained {abs_delta:.1f}s. Good compound choice!"
        )
    if delta > 0:
        return f"Lost {abs_delta:.1f}s vs actual over this stint."
    return f"Gained {abs_delta:.1f}s vs actual — strong stint!"


def model_info(race_model: dict) -> dict:
    observed = race_model["observed"]
    return {
        "observed_compounds": observed,
        "unmodeled_compounds": race_model["unmodeled"],
        "pace_note": race_model["pace_note"],
        "fuel_source": race_model["fuel_source"],
        "fuel_corrected": True,
        "wet": race_model["wet"],
        "min_compounds": 1 if len(observed) < 2 else 2,
        "neutral_laps": len(race_model["neutral"]),
    }
