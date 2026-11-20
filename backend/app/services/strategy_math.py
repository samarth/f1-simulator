"""Pure lap-time and strategy maths.

No network and no FastF1/OpenF1 objects. Race services hand in plain rows.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

DRY_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
WET_COMPOUNDS = ("INTERMEDIATE", "WET")
ALL_COMPOUNDS = DRY_COMPOUNDS + WET_COMPOUNDS
# Published fuel effect is about 0.03–0.06s per lap of fuel burned.
# Used only when this race does not identify one.
STANDARD_FUEL_PER_LAP = 0.04
MIN_STINT = 5


def laps_remaining(race_lap: int, total_laps: int) -> int:
    return max(total_laps - race_lap, 0)


def fuel_penalty(race_lap: int, total_laps: int, fuel_per_lap: float) -> float:
    """Extra seconds from fuel still in the car, relative to the last lap."""
    return laps_remaining(race_lap, total_laps) * fuel_per_lap


def estimate_lap_time(
    models: dict,
    compound: str,
    tyre_life: int,
    race_lap: int,
    total_laps: int,
    fuel_per_lap: float,
    driver_offset: float = 0.0,
    field_pace: dict[int, float] | None = None,
) -> float:
    """Fuel-corrected tire model, with fuel and the driver's pace added back.

    In a mixed wet/dry race ``field_pace`` is the field's recorded pace on that
    lap. The compound then only adds its measured gap to the field, so a dry
    tire cannot invent a dry-track lap time in the middle of the wet.
    """
    life = max(int(tyre_life), 1)
    model = models.get(compound)
    pace = _nearby_field_pace(field_pace, race_lap) if field_pace else None
    if pace is not None and model and model.get("field_relative"):
        typical = float(model.get("typical_life", 1))
        return (
            pace
            + float(model.get("delta", 0.0))
            + float(model["deg_rate"]) * (life - typical)
            + driver_offset
        )
    if model:
        corrected = float(model["base_time"]) + float(model["deg_rate"]) * life
    elif models:
        corrected = float(np.mean([m["base_time"] + m["deg_rate"] * life for m in models.values()]))
    else:
        corrected = 95.0
    return corrected + fuel_penalty(race_lap, total_laps, fuel_per_lap) + driver_offset


def _nearby_field_pace(field_pace: dict[int, float] | None, race_lap: int) -> float | None:
    """Field pace on this lap, or on a lap a couple either side when this one is thin."""
    if not field_pace:
        return None
    if race_lap in field_pace:
        return float(field_pace[race_lap])
    nearest = min(field_pace, key=lambda lap: (abs(lap - race_lap), lap))
    if abs(nearest - race_lap) <= 2:
        return float(field_pace[nearest])
    return None


def _finite(value) -> bool:
    return value is not None and not (isinstance(value, float) and np.isnan(value))


def neutral_lap_numbers(rows: list[dict], threshold: float = 3.5) -> set[int]:
    """Laps where the whole field was slow: safety car, virtual safety car, red flag.

    A red-flag lap is often flagged as a pit out for the whole field, so it never
    appears in the non-pit sample. Those laps are included when the field median
    is far beyond a normal pit stop.
    """
    racing: dict[int, list[float]] = defaultdict(list)
    everyone: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if not _finite(row.get("time")):
            continue
        everyone[int(row["lap"])].append(float(row["time"]))
        if row.get("pit_in") or row.get("pit_out"):
            continue
        racing[int(row["lap"])].append(float(row["time"]))
    if len(everyone) < 5:
        return set()
    racing_medians = {lap: float(np.median(times)) for lap, times in racing.items() if len(times) >= 2}
    if racing_medians:
        baseline = float(np.quantile(list(racing_medians.values()), 0.4))
    else:
        baseline = float(np.quantile([float(np.median(times)) for times in everyone.values()], 0.4))
    neutral = {lap for lap, median in racing_medians.items() if median > baseline + threshold}
    for lap, times in everyone.items():
        if lap in neutral or len(times) < 2:
            continue
        # Almost nobody set a green lap, and the pack was far slower than a pit stop.
        green = len(racing.get(lap, []))
        if green * 3 <= len(times) and float(np.median(times)) > baseline + 40:
            neutral.add(lap)
    return neutral


def field_neutral_times(rows: list[dict], neutral: set[int]) -> dict[int, float]:
    """Recorded pace of a neutralized lap, including cars flagged as pitting.

    A red-flag restart is often marked as a pit out for the whole field. Skipping
    those rows would leave the lap with no time, and the model would invent a
    green-flag lap in its place.
    """
    by_lap: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        lap = int(row["lap"])
        if lap not in neutral or not _finite(row.get("time")):
            continue
        by_lap[lap].append(float(row["time"]))
    return {lap: float(np.median(times)) for lap, times in by_lap.items() if times}


def is_wet_race(rows: list[dict], rainfall: bool = False) -> bool:
    wet = 0
    dry = 0
    for row in rows:
        if not _finite(row.get("time")) or row.get("pit_in") or row.get("pit_out"):
            continue
        compound = row.get("compound")
        if compound in WET_COMPOUNDS:
            wet += 1
        elif compound in DRY_COMPOUNDS:
            dry += 1
    if wet == 0:
        return False
    if wet > dry:
        return True
    return bool(rainfall and wet >= 15)


def estimate_fuel_per_lap(rows: list[dict], neutral: set[int]) -> tuple[float, str]:
    """Shared fuel coefficient. Needs drivers who ran a compound for two stints.

    Within one stint, tyre life and fuel burn move together, so a single stint
    cannot separate them. Two stints can.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        if not _clean_model_lap(row, neutral):
            continue
        groups[(row["driver"], row["compound"])].append(row)

    fuels: list[float] = []
    weights: list[int] = []
    for group in groups.values():
        stints = {row["stint"] for row in group}
        if len(group) < 8 or len(stints) < 2:
            continue
        times = np.array([row["time"] for row in group], dtype=float)
        life = np.array([row["tyre_life"] for row in group], dtype=float)
        remaining = np.array([row["laps_remaining"] for row in group], dtype=float)
        if np.std(remaining) < 1 or np.std(life) < 1:
            continue
        correlation = np.corrcoef(life, remaining)[0, 1]
        if not np.isfinite(correlation) or abs(correlation) > 0.95:
            continue
        design = np.column_stack([life - life.mean(), remaining - remaining.mean()])
        coef, _, _, _ = np.linalg.lstsq(design, times - times.mean(), rcond=None)
        fuel = float(coef[1])
        if 0.01 <= fuel <= 0.09:
            fuels.append(fuel)
            weights.append(len(group))
    if not fuels:
        return STANDARD_FUEL_PER_LAP, "standard"
    total = float(sum(weights))
    estimate = float(sum(fuel * weight for fuel, weight in zip(fuels, weights)) / total)
    return estimate, "estimated"


def _clean_model_lap(row: dict, neutral: set[int]) -> bool:
    return (
        _finite(row.get("time"))
        and not row.get("pit_in")
        and not row.get("pit_out")
        and int(row["lap"]) not in neutral
        and row.get("compound") in ALL_COMPOUNDS
    )


def fit_compound_models(rows: list[dict], neutral: set[int], fuel_per_lap: float) -> dict:
    """Per-compound fuel-corrected base time and degradation.

    Only compounds with enough clean laps are returned. Nothing is invented.
    """
    by_compound: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if _clean_model_lap(row, neutral):
            by_compound[row["compound"]].append(row)

    models = {}
    for compound, compound_rows in by_compound.items():
        if len(compound_rows) < 10:
            continue
        slopes = []
        corrected_levels = []
        stints: dict[tuple, list[dict]] = defaultdict(list)
        for row in compound_rows:
            stints[(row["driver"], row["stint"])].append(row)
        usable_rows = []
        for stint_rows in stints.values():
            if len(stint_rows) < 4:
                continue
            stint_rows = sorted(stint_rows, key=lambda row: row["tyre_life"])
            life = np.array([row["tyre_life"] for row in stint_rows], dtype=float)
            corrected = np.array(
                [row["time"] - fuel_per_lap * row["laps_remaining"] for row in stint_rows],
                dtype=float,
            )
            center = float(np.median(corrected))
            spread = float(np.std(corrected))
            if spread > 0:
                keep = np.abs(corrected - center) <= max(2.5 * spread, 1.5)
                if int(keep.sum()) >= 4:
                    life = life[keep]
                    corrected = corrected[keep]
                    stint_rows = [row for row, flag in zip(stint_rows, keep) if flag]
            if len(life) >= 4 and np.std(life) > 0:
                slope = float(np.polyfit(life, corrected, 1)[0])
                if -0.05 <= slope <= 0.25:
                    slopes.append(slope)
            for row, level in zip(stint_rows, corrected):
                corrected_levels.append((float(level), int(row["tyre_life"])))
                usable_rows.append(row)
        if len(usable_rows) < 10:
            continue
        # One short stint produces a noisy slope. Prefer a modest default then.
        enough_slope = len(slopes) >= 2 or len(usable_rows) >= 20
        if slopes and enough_slope:
            deg = max(float(np.median(slopes)), 0.0)
        else:
            deg = {"SOFT": 0.05, "MEDIUM": 0.035, "HARD": 0.025, "INTERMEDIATE": 0.04, "WET": 0.05}.get(
                compound, 0.04
            )
        base_samples = [level - deg * life for level, life in corrected_levels]
        models[compound] = {
            "base_time": float(np.median(base_samples)),
            "deg_rate": deg,
            "observed": True,
            "sample_laps": len(usable_rows),
        }
    return models


def pace_order_note(models: dict) -> str:
    """Describe a dry-compound order that does not match the usual soft-medium-hard pace."""
    present = [compound for compound in DRY_COMPOUNDS if compound in models]
    if len(present) < 2:
        return ""
    relative = any(models[compound].get("field_relative") for compound in present)
    if relative:
        # Absolute bases come from different parts of a mixed race. Compare gaps to the field.
        fresh = {compound: float(models[compound].get("delta", 0.0)) for compound in present}
    else:
        fresh = {
            compound: models[compound]["base_time"] + models[compound]["deg_rate"]
            for compound in present
        }
    expected = sorted(present, key=lambda compound: DRY_COMPOUNDS.index(compound))
    measured = sorted(present, key=lambda compound: fresh[compound])
    if measured == expected:
        return ""
    # Ignore an inversion smaller than the noise in a lap time.
    worst = 0.0
    for index, compound in enumerate(expected):
        for earlier in expected[:index]:
            worst = max(worst, fresh[earlier] - fresh[compound])
    if worst < 0.15:
        return ""
    if relative:
        parts = [f"{compound.lower()} {fresh[compound]:+.2f}s vs the field" for compound in measured]
        described = "Measured gap to the field"
    else:
        parts = [f"{compound.lower()} {fresh[compound]:.2f}s" for compound in measured]
        described = "Measured fresh pace, fuel-corrected,"
    return (
        f"{described} does not follow the usual "
        f"soft-medium-hard order ({' faster than '.join(parts)}). "
        "Suggestions use the measured pace rather than an assumed order. "
        "Small samples, traffic, or a track that sped up can cause this."
    )


def unmodeled_compounds(rows: list[dict], models: dict) -> list[str]:
    seen = []
    for row in rows:
        compound = row.get("compound")
        if compound in ALL_COMPOUNDS and compound not in models and compound not in seen:
            if any(_finite(other.get("time")) and other.get("compound") == compound for other in rows):
                seen.append(compound)
    return seen


def field_pace_by_lap(rows: list[dict], neutral: set[int]) -> dict[int, float]:
    """Median green-flag lap time of the field, lap by lap. This carries the conditions."""
    by_lap: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if not _clean_model_lap(row, neutral):
            continue
        by_lap[int(row["lap"])].append(float(row["time"]))
    return {lap: float(np.median(times)) for lap, times in by_lap.items() if len(times) >= 2}


def attach_field_deltas(models: dict, rows: list[dict], neutral: set[int], field_pace: dict[int, float]) -> None:
    """Express each compound as a gap to the field pace on the laps it actually ran."""
    for compound, model in models.items():
        lives = []
        samples = []
        for row in rows:
            if row.get("compound") != compound or not _clean_model_lap(row, neutral):
                continue
            if int(row["lap"]) not in field_pace:
                continue
            lives.append(int(row["tyre_life"]))
            samples.append(row)
        typical = float(np.median(lives)) if lives else 1.0
        gaps = []
        for row in samples:
            wear = float(model["deg_rate"]) * (int(row["tyre_life"]) - typical)
            gaps.append(float(row["time"]) - field_pace[int(row["lap"])] - wear)
        model["typical_life"] = typical
        model["delta"] = float(np.median(gaps)) if gaps else 0.0
        model["field_relative"] = True


def driver_pace_offset(
    rows: list[dict],
    models: dict,
    neutral: set[int],
    fuel_per_lap: float,
    total_laps: int,
    driver: str,
    field_pace: dict[int, float] | None = None,
) -> float:
    """Mean gap so this driver's clean laps sit on their own pace, not the field's."""
    residuals = []
    for row in rows:
        if row.get("driver") != driver or not _clean_model_lap(row, neutral):
            continue
        if row["compound"] not in models:
            continue
        predicted = estimate_lap_time(
            models,
            row["compound"],
            row["tyre_life"],
            row["lap"],
            total_laps,
            fuel_per_lap,
            field_pace=field_pace,
        )
        residuals.append(float(row["time"]) - predicted)
    if len(residuals) < 5:
        return 0.0
    return float(np.mean(residuals))


def lane_time_pit_loss(durations: list[float]) -> float | None:
    """Median pit-lane time. Ignores stationary-only readings and red-flag outliers."""
    lane = [float(value) for value in durations if value is not None and 15 <= float(value) <= 40]
    if len(lane) < 3:
        return None
    return float(np.median(lane))


def empirical_pit_losses(
    rows: list[dict],
    models: dict,
    neutral: set[int],
    fuel_per_lap: float,
    total_laps: int,
    driver_offsets: dict[str, float],
    field_pace: dict[int, float] | None = None,
) -> dict[str, list[float]]:
    """Extra seconds of an in-lap plus out-lap versus two racing laps.

    This does not trust ``pit_duration``, which is sometimes the full lane
    pass and sometimes only the stationary time.
    """
    by_driver: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_driver[row["driver"]].append(row)
    losses: dict[str, list[float]] = {}
    for driver, driver_rows in by_driver.items():
        ordered = sorted(driver_rows, key=lambda row: row["lap"])
        offset = driver_offsets.get(driver, 0.0)
        driver_losses = []
        for index, row in enumerate(ordered[:-1]):
            if not row.get("pit_in"):
                continue
            nxt = ordered[index + 1]
            if nxt["lap"] != row["lap"] + 1:
                continue
            if row["lap"] in neutral or nxt["lap"] in neutral:
                continue
            if not _finite(row.get("time")) or not _finite(nxt.get("time")):
                continue
            if row["compound"] not in models or nxt["compound"] not in models:
                continue
            pred_in = estimate_lap_time(
                models, row["compound"], row["tyre_life"], row["lap"], total_laps, fuel_per_lap, offset, field_pace
            )
            pred_out = estimate_lap_time(
                models, nxt["compound"], nxt["tyre_life"], nxt["lap"], total_laps, fuel_per_lap, offset, field_pace
            )
            loss = (float(row["time"]) + float(nxt["time"])) - (pred_in + pred_out)
            if 10 <= loss <= 40:
                driver_losses.append(float(loss))
        if driver_losses:
            losses[driver] = driver_losses
    return losses


def choose_pit_loss(
    driver_losses: list[float],
    field_losses: list[float],
    lane_loss: float | None,
) -> tuple[float, str]:
    if driver_losses:
        return float(np.mean(driver_losses)), "lap_delta"
    if field_losses:
        return float(np.median(field_losses)), "field_lap_delta"
    if lane_loss is not None:
        return lane_loss, "lane_time"
    return 22.0, "default"


def green_rmse(
    rows: list[dict],
    models: dict,
    neutral: set[int],
    fuel_per_lap: float,
    total_laps: int,
    driver: str,
    driver_offset: float,
    field_pace: dict[int, float] | None = None,
) -> float | None:
    errors = []
    for row in rows:
        if row.get("driver") != driver or not _clean_model_lap(row, neutral):
            continue
        if row["compound"] not in models:
            continue
        predicted = estimate_lap_time(
            models, row["compound"], row["tyre_life"], row["lap"], total_laps, fuel_per_lap, driver_offset, field_pace
        )
        errors.append(float(row["time"]) - predicted)
    if len(errors) < 5:
        return None
    return float(np.sqrt(np.mean(np.square(errors))))


def with_opening_tyre_age(stints: list[dict], compound: str | None, age: int) -> list[dict]:
    """Use the tires the car actually started on when the plan starts on that compound.

    The age is omitted, not zero, when the caller did not choose one. A plan
    that starts on a different compound is a fresh set.
    """
    copied = [dict(stint) for stint in stints]
    if not copied or not compound or age <= 0:
        return copied
    if copied[0].get("start_tyre_age") is not None:
        return copied
    if copied[0].get("compound") != compound:
        return copied
    copied[0]["start_tyre_age"] = int(age)
    return copied


def simulate_strategy(
    models: dict,
    stints: list[dict],
    pit_loss: float,
    total_laps: int,
    fuel_per_lap: float,
    driver_offset: float = 0.0,
    neutral_times: dict[int, float] | None = None,
    field_pace: dict[int, float] | None = None,
) -> list[dict]:
    """One racing lap per planned lap. Pit loss is added once, on the out-lap.

    The loss is the extra time of the in-lap and the out-lap together. The
    recorded lap that carries it is the out-lap, so the model adds it there
    and leaves the in-lap as a racing lap. Neutralised laps use the recorded
    time and are not charged again.
    """
    neutral_times = neutral_times or {}
    results = []
    current_lap = 1
    pending_pit = 0.0
    for stint_index, stint in enumerate(stints):
        compound = stint["compound"]
        num_laps = int(stint["laps"])
        age = int(stint.get("start_tyre_age") or 0)
        for lap_in_stint in range(num_laps):
            tyre_life = age + lap_in_stint + 1
            is_pit = lap_in_stint == num_laps - 1 and stint_index < len(stints) - 1
            if current_lap in neutral_times:
                # The whole field was neutralized. A pit on this lap is not charged
                # again; the recorded lap already contains whatever happened.
                lap_time = float(neutral_times[current_lap])
                neutral = True
                pending_pit = 0.0
            else:
                lap_time = estimate_lap_time(
                    models, compound, tyre_life, current_lap, total_laps, fuel_per_lap, driver_offset, field_pace
                )
                neutral = False
                if pending_pit:
                    lap_time += pending_pit
                    pending_pit = 0.0
                if is_pit:
                    pending_pit = float(pit_loss)
            results.append(
                {
                    "lap": current_lap,
                    "time_sec": float(lap_time),
                    "compound": compound,
                    "tyre_life": int(tyre_life),
                    "is_pit_lap": is_pit,
                    "neutral": neutral,
                }
            )
            current_lap += 1
    if pending_pit and results and not results[-1]["neutral"]:
        results[-1]["time_sec"] += pending_pit
    return results


def compared_total(simulated: list[dict], actual_by_lap: dict[int, float]) -> float:
    """Sum of modelled times on laps the driver actually recorded."""
    return float(sum(lap["time_sec"] for lap in simulated if lap["lap"] in actual_by_lap))


def replay_residual(simulated: list[dict], actual_by_lap: dict[int, float]) -> dict:
    common = [lap for lap in simulated if lap["lap"] in actual_by_lap]
    if not common:
        return {
            "replay_time": 0.0,
            "actual_time": 0.0,
            "residual_seconds": 0.0,
            "residual_per_lap": 0.0,
            "timed_laps": 0,
        }
    replay = float(sum(lap["time_sec"] for lap in common))
    actual = float(sum(actual_by_lap[lap["lap"]] for lap in common))
    residual = replay - actual
    return {
        "replay_time": round(replay, 3),
        "actual_time": round(actual, 3),
        "residual_seconds": round(residual, 3),
        "residual_per_lap": round(residual / len(common), 3),
        "timed_laps": len(common),
    }


def degradation_series(
    rows: list[dict],
    models: dict,
    neutral: set[int],
    fuel_per_lap: float,
) -> dict:
    """Fuel-corrected mean lap time by tyre life, for the chart."""
    series = {}
    for compound in models:
        bucket: dict[int, list[float]] = defaultdict(list)
        for row in rows:
            if row.get("compound") != compound or not _clean_model_lap(row, neutral):
                continue
            corrected = float(row["time"]) - fuel_per_lap * float(row["laps_remaining"])
            bucket[int(row["tyre_life"])].append(corrected)
        points = []
        for life, times in bucket.items():
            if len(times) < 2:
                continue
            arr = np.array(times, dtype=float)
            center = float(np.median(arr))
            spread = float(np.std(arr))
            if spread > 0:
                arr = arr[np.abs(arr - center) <= max(2 * spread, 1.0)]
            if len(arr) == 0:
                continue
            points.append((life, float(np.mean(arr)), float(np.std(arr)) if len(arr) > 1 else 0.0, int(len(arr))))
        if not points:
            continue
        points.sort()
        series[compound] = {
            "tyre_life": [point[0] for point in points],
            "avg_lap_time": [point[1] for point in points],
            "std_lap_time": [point[2] for point in points],
            "count": [point[3] for point in points],
        }
    return series


def fuel_effect_payload(total_laps: int, fuel_per_lap: float, source: str) -> dict:
    laps = list(range(1, total_laps + 1))
    penalties = [fuel_penalty(lap, total_laps, fuel_per_lap) for lap in laps]
    corrected = source == "estimated" or source == "standard"
    if source == "estimated":
        how = "estimated from this race"
    else:
        how = "a standard 40ms per lap, because this race did not separate fuel from tire wear"
    return {
        "laps": laps,
        "fuel_penalty_seconds": penalties,
        "fuel_effect_per_lap": fuel_per_lap,
        "total_fuel_effect": round(fuel_penalty(1, total_laps, fuel_per_lap), 3),
        "source": source,
        "fuel_corrected": corrected,
        "description": (
            f"Fuel-corrected curves remove about {fuel_per_lap * 1000:.0f}ms per lap of fuel still on board ({how}). "
            "Lap predictions add that fuel back."
        ),
    }


def strategy_uses_only(stints: list[dict], allowed: set[str]) -> bool:
    return all(stint["compound"] in allowed for stint in stints)


def has_consecutive_repeat(stints: list[dict]) -> bool:
    compounds = [stint["compound"] for stint in stints]
    return any(compounds[i] == compounds[i + 1] for i in range(len(compounds) - 1))


def compound_usage(rows: list[dict], min_drivers: int = 1) -> dict[str, set[int]]:
    """Laps on which enough drivers actually ran each compound."""
    counts: dict[tuple[str, int], set] = defaultdict(set)
    for row in rows:
        compound = row.get("compound")
        if compound in ALL_COMPOUNDS and _finite(row.get("time")):
            counts[(compound, int(row["lap"]))].add(row.get("driver"))
    usage: dict[str, set[int]] = defaultdict(set)
    for (compound, lap), drivers in counts.items():
        if len(drivers) >= min_drivers:
            usage[compound].add(lap)
    return dict(usage)


def expand_usage(usage: dict[str, set[int]], margin: int = 2) -> dict[str, set[int]]:
    """Allow a couple of laps either side of where a compound was really used."""
    expanded: dict[str, set[int]] = {}
    for compound, laps in usage.items():
        covered: set[int] = set()
        for lap in laps:
            covered.update(range(lap - margin, lap + margin + 1))
        expanded[compound] = {lap for lap in covered if lap >= 1}
    return expanded


def longest_observed_stint(rows: list[dict]) -> dict[str, int]:
    """Longest timed stint of each compound. Suggestions should not run past this."""
    counts: dict[tuple, int] = defaultdict(int)
    for row in rows:
        compound = row.get("compound")
        if compound not in ALL_COMPOUNDS or not _finite(row.get("time")):
            continue
        counts[(row.get("driver"), row.get("stint"), compound)] += 1
    longest: dict[str, int] = defaultdict(int)
    for (_, _, compound), count in counts.items():
        longest[compound] = max(longest[compound], count)
    return dict(longest)


def stint_fits_usage(stints: list[dict], usage: dict[str, set[int]]) -> bool:
    """Every planned lap has to sit where that compound was actually used."""
    lap = 1
    for stint in stints:
        allowed = usage.get(stint["compound"])
        if not allowed:
            return False
        for offset in range(int(stint["laps"])):
            if lap + offset not in allowed:
                return False
        lap += int(stint["laps"])
    return True


def stint_respects_length(stints: list[dict], max_laps: dict[str, int]) -> bool:
    return all(int(stint["laps"]) <= max_laps.get(stint["compound"], 0) for stint in stints)


def suggestion_is_legal(stints: list[dict], observed: list[str], wet: bool) -> bool:
    """Legal suggestion: observed compounds only, no back-to-back repeat, two compounds when possible."""
    if not stints or not strategy_uses_only(stints, set(observed)):
        return False
    if has_consecutive_repeat(stints):
        return False
    unique = {stint["compound"] for stint in stints}
    if len(observed) >= 2 and len(unique) < 2:
        return False
    if not wet:
        dry = [compound for compound in unique if compound in DRY_COMPOUNDS]
        observed_dry = [compound for compound in observed if compound in DRY_COMPOUNDS]
        if len(observed_dry) >= 2 and len(dry) < 2:
            return False
    return True


def user_plan_problem(stints: list[dict], observed: list[str], wet: bool) -> str | None:
    """What to tell the user when their own plan cannot be simulated. Repeats are allowed."""
    allowed = set(observed)
    unknown = [stint["compound"] for stint in stints if stint["compound"] not in allowed]
    if unknown:
        names = ", ".join(sorted(set(unknown)))
        return f"{names} was not used enough in this race to model. Available: {', '.join(observed)}."
    unique = {stint["compound"] for stint in stints}
    if len(observed) >= 2 and len(unique) < 2:
        return "Use at least two different compounds. This race has more than one modelled tire."
    if not wet:
        dry = {compound for compound in unique if compound in DRY_COMPOUNDS}
        observed_dry = [compound for compound in observed if compound in DRY_COMPOUNDS]
        if len(observed_dry) >= 2 and len(dry) < 2:
            return "A dry race needs at least two different dry compounds (soft, medium, or hard)."
    return None


def find_optimal_strategies(
    models: dict,
    pit_loss: float,
    total_laps: int,
    fuel_per_lap: float,
    driver_offset: float = 0.0,
    neutral_times: dict[int, float] | None = None,
    wet: bool = False,
    windows: dict[str, set[int]] | None = None,
    mixed: bool = False,
    field_pace: dict[int, float] | None = None,
    max_stint: dict[str, int] | None = None,
    opening_compound: str | None = None,
    opening_age: int = 0,
) -> dict:
    """Best 1-stop, 2-stop, and 3-stop plans on observed compounds only.

    ``windows`` is the set of laps each compound was actually used (already
    expanded by a small margin). ``max_stint`` is the longest stint anyone
    completed on that compound. Both keep a suggestion inside what the race showed.
    ``mixed`` is accepted so older callers keep working; the lap sets already
    encode a wet phase.
    """
    compounds = [compound for compound in ALL_COMPOUNDS if compound in models]
    if len(compounds) < 2:
        return {}
    best: dict[int, tuple[float, list[dict]]] = {}
    n = total_laps

    def consider(num_stops: int, stints: list[dict]) -> None:
        if not suggestion_is_legal(stints, compounds, wet):
            return
        if windows and not stint_fits_usage(stints, windows):
            return
        if max_stint and not stint_respects_length(stints, max_stint):
            return
        stints = with_opening_tyre_age(stints, opening_compound, opening_age)
        laps = simulate_strategy(
            models, stints, pit_loss, n, fuel_per_lap, driver_offset, neutral_times, field_pace
        )
        total = sum(lap["time_sec"] for lap in laps)
        if num_stops not in best or total < best[num_stops][0]:
            best[num_stops] = (total, stints)

    for pit1 in range(MIN_STINT, n - MIN_STINT + 1, 2):
        for first in compounds:
            for second in compounds:
                consider(
                    1,
                    [
                        {"compound": first, "laps": pit1},
                        {"compound": second, "laps": n - pit1},
                    ],
                )

    for pit1 in range(MIN_STINT, n - 2 * MIN_STINT + 1, 3):
        for pit2 in range(pit1 + MIN_STINT, n - MIN_STINT + 1, 3):
            for first in compounds:
                for second in compounds:
                    for third in compounds:
                        consider(
                            2,
                            [
                                {"compound": first, "laps": pit1},
                                {"compound": second, "laps": pit2 - pit1},
                                {"compound": third, "laps": n - pit2},
                            ],
                        )

    if n >= 4 * MIN_STINT:
        for pit1 in range(MIN_STINT, n - 3 * MIN_STINT + 1, 5):
            for pit2 in range(pit1 + MIN_STINT, n - 2 * MIN_STINT + 1, 5):
                for pit3 in range(pit2 + MIN_STINT, n - MIN_STINT + 1, 5):
                    for first in compounds:
                        for second in compounds:
                            for third in compounds:
                                for fourth in compounds:
                                    consider(
                                        3,
                                        [
                                            {"compound": first, "laps": pit1},
                                            {"compound": second, "laps": pit2 - pit1},
                                            {"compound": third, "laps": pit3 - pit2},
                                            {"compound": fourth, "laps": n - pit3},
                                        ],
                                    )
    return best
