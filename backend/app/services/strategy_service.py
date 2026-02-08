import numpy as np
import pandas as pd

from .session_service import load_session

# Fuel effect: approximately 0.055s per lap faster as fuel burns off
# F1 cars start with ~110kg fuel, burn ~1.8kg/lap, ~0.03s/kg delta
FUEL_EFFECT_PER_LAP = 0.055  # seconds gained per lap from fuel burn-off


def get_race_degradation_data(session, fuel_corrected: bool = True) -> dict:
    """Extract tire degradation curves from a race session.
    
    Uses per-stint analysis to avoid fuel load confounding the results.
    """
    laps = session.laps
    degradation = {}

    for compound in ["SOFT", "MEDIUM", "HARD"]:
        try:
            compound_laps = laps.pick_compounds(compound)
            clean_laps = compound_laps.pick_wo_box().pick_accurate()

            if "TrackStatus" in clean_laps.columns:
                clean_laps = clean_laps[
                    clean_laps["TrackStatus"].isin(["1", "2", 1, 2])
                    | clean_laps["TrackStatus"].isna()
                ]

            if clean_laps.empty:
                continue

            clean_laps = clean_laps.copy()
            clean_laps["LapTimeSec"] = clean_laps["LapTime"].dt.total_seconds()

            mean_time = clean_laps["LapTimeSec"].mean()
            std_time = clean_laps["LapTimeSec"].std()
            if std_time > 0:
                clean_laps = clean_laps[
                    (clean_laps["LapTimeSec"] >= mean_time - 2 * std_time)
                    & (clean_laps["LapTimeSec"] <= mean_time + 2 * std_time)
                ]

            if clean_laps.empty:
                continue

            # Group by tyre life for the visualization
            grouped = clean_laps.groupby("TyreLife")["LapTimeSec"].agg(["mean", "std", "count"])
            grouped = grouped[grouped["count"] >= 2]

            if grouped.empty:
                grouped = clean_laps.groupby("TyreLife")["LapTimeSec"].agg(["mean", "std", "count"])

            if grouped.empty:
                continue

            degradation[compound] = {
                "tyre_life": grouped.index.tolist(),
                "avg_lap_time": grouped["mean"].tolist(),
                "std_lap_time": grouped["std"].fillna(0).tolist(),
                "count": grouped["count"].tolist(),
            }
        except Exception as e:
            print(f"Error processing compound {compound}: {e}")
            continue

    return degradation


def build_degradation_model(session) -> dict:
    """Build degradation models using per-stint analysis.
    
    This approach calculates degradation within each stint (where fuel is roughly constant),
    then averages across stints. This avoids the fuel load confounding the results.
    """
    laps = session.laps
    models = {}
    
    for compound in ["SOFT", "MEDIUM", "HARD"]:
        try:
            compound_laps = laps.pick_compounds(compound).pick_wo_box().pick_accurate()
            if compound_laps.empty:
                continue
            
            degradation_rates = []
            base_times = []
            
            # Group by driver and stint
            for (driver, stint), stint_laps in compound_laps.groupby(['Driver', 'Stint']):
                stint_laps = stint_laps.sort_values('TyreLife')
                if len(stint_laps) < 3:  # Need at least 3 laps for meaningful regression
                    continue
                
                tyre_life = stint_laps['TyreLife'].values
                lap_times = stint_laps['LapTime'].dt.total_seconds().values
                
                # Remove outliers
                mean_time = np.mean(lap_times)
                std_time = np.std(lap_times)
                if std_time > 0:
                    mask = np.abs(lap_times - mean_time) < 2 * std_time
                    if mask.sum() < 3:
                        continue
                    tyre_life = tyre_life[mask]
                    lap_times = lap_times[mask]
                
                coeffs = np.polyfit(tyre_life, lap_times, 1)
                deg_rate = coeffs[0]  # slope
                base_time = coeffs[1]  # intercept
                
                # Only include reasonable degradation rates (0 to 200ms/lap)
                if 0 < deg_rate < 0.2:
                    degradation_rates.append(deg_rate)
                    base_times.append(base_time)
            
            if degradation_rates:
                models[compound] = {
                    "base_time": float(np.mean(base_times)),
                    "deg_rate": float(np.mean(degradation_rates)),
                }
        except Exception as e:
            print(f"Error building model for {compound}: {e}")
            continue
    
    # If we couldn't calculate models for some compounds, use reasonable defaults
    # based on typical F1 tire behavior
    default_base = 95.0
    if "SOFT" not in models and "MEDIUM" not in models and "HARD" not in models:
        # No data at all, use typical values
        models = {
            "SOFT": {"base_time": default_base - 0.5, "deg_rate": 0.065},
            "MEDIUM": {"base_time": default_base, "deg_rate": 0.045},
            "HARD": {"base_time": default_base + 0.5, "deg_rate": 0.030},
        }
    else:
        # Fill in missing compounds with relative estimates
        if models:
            avg_base = np.mean([m["base_time"] for m in models.values()])
            if "SOFT" not in models:
                models["SOFT"] = {"base_time": avg_base - 0.5, "deg_rate": 0.065}
            if "MEDIUM" not in models:
                models["MEDIUM"] = {"base_time": avg_base, "deg_rate": 0.045}
            if "HARD" not in models:
                models["HARD"] = {"base_time": avg_base + 0.5, "deg_rate": 0.030}
    
    return models


def get_fuel_effect_data(total_laps: int = 57) -> dict:
    """Return data showing how fuel burn-off affects lap times."""
    laps = list(range(1, total_laps + 1))
    # Time penalty from fuel weight (relative to end of race)
    fuel_penalty = [(total_laps - lap) * FUEL_EFFECT_PER_LAP for lap in laps]
    
    return {
        "laps": laps,
        "fuel_penalty_seconds": fuel_penalty,
        "fuel_effect_per_lap": FUEL_EFFECT_PER_LAP,
        "total_fuel_effect": total_laps * FUEL_EFFECT_PER_LAP,
        "description": f"Cars lose ~{int(FUEL_EFFECT_PER_LAP * 1000)}ms per lap of fuel carried. Total effect over {total_laps} laps: ~{total_laps * FUEL_EFFECT_PER_LAP:.1f}s"
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
            "conditions": "Unknown"
        }
    
    # Get average/representative values
    air_temp = weather["AirTemp"].mean() if "AirTemp" in weather.columns else None
    track_temp = weather["TrackTemp"].mean() if "TrackTemp" in weather.columns else None
    humidity = weather["Humidity"].mean() if "Humidity" in weather.columns else None
    rainfall = bool(weather["Rainfall"].max() > 0) if "Rainfall" in weather.columns else False
    wind_speed = weather["WindSpeed"].mean() if "WindSpeed" in weather.columns else None
    
    # Determine conditions description
    if rainfall:
        conditions = "Wet"
    elif track_temp and track_temp > 40:
        conditions = "Hot"
    elif track_temp and track_temp < 20:
        conditions = "Cool"
    else:
        conditions = "Dry"
    
    return {
        "available": True,
        "air_temp": round(float(air_temp), 1) if air_temp else None,
        "track_temp": round(float(track_temp), 1) if track_temp else None,
        "humidity": round(float(humidity), 1) if humidity else None,
        "rainfall": rainfall,
        "wind_speed": round(float(wind_speed), 1) if wind_speed else None,
        "conditions": conditions,
        "track_temp_min": round(float(weather["TrackTemp"].min()), 1) if "TrackTemp" in weather.columns else None,
        "track_temp_max": round(float(weather["TrackTemp"].max()), 1) if "TrackTemp" in weather.columns else None,
    }


def get_pit_stop_stats(session) -> dict:
    """Extract average pit stop duration from the race."""
    laps = session.laps
    pit_times = []
    drivers = laps["Driver"].unique()

    for driver in drivers:
        driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
        for _, lap in driver_laps.iterrows():
            if pd.notna(lap.get("PitInTime")) and pd.notna(lap.get("PitOutTime")):
                pit_duration = (lap["PitOutTime"] - lap["PitInTime"]).total_seconds()
                if 15 < pit_duration < 60:
                    pit_times.append(pit_duration)

    if not pit_times:
        for driver in drivers:
            driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
            for i in range(1, len(driver_laps)):
                cur = driver_laps.iloc[i]
                prev = driver_laps.iloc[i - 1]
                if (
                    pd.notna(cur.get("Stint"))
                    and pd.notna(prev.get("Stint"))
                    and cur["Stint"] != prev["Stint"]
                ):
                    if pd.notna(cur["LapTime"]) and pd.notna(prev["LapTime"]):
                        avg_clean = laps.pick_wo_box().pick_accurate()
                        if not avg_clean.empty:
                            avg_time = avg_clean["LapTime"].dt.total_seconds().mean()
                            pit_loss = cur["LapTime"].total_seconds() - avg_time
                            if 15 < pit_loss < 40:
                                pit_times.append(pit_loss)

    if pit_times:
        return {
            "avg_pit_time": float(np.mean(pit_times)),
            "min_pit_time": float(np.min(pit_times)),
            "max_pit_time": float(np.max(pit_times)),
            "num_stops": len(pit_times),
        }
    return {"avg_pit_time": 22.0, "min_pit_time": 20.0, "max_pit_time": 25.0, "num_stops": 0}


def get_driver_actual_strategy(session, driver: str) -> dict | None:
    """Extract what a driver actually did: stints, compounds, lap counts, total time."""
    laps = session.laps
    driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")

    if driver_laps.empty:
        return None

    stints = []
    current_stint = None

    for _, lap in driver_laps.iterrows():
        stint_num = lap.get("Stint", 1)
        compound = lap.get("Compound", "UNKNOWN")

        if current_stint is None or current_stint["stint"] != stint_num:
            if current_stint is not None:
                stints.append(current_stint)
            current_stint = {
                "stint": int(stint_num),
                "compound": str(compound),
                "start_lap": int(lap["LapNumber"]),
                "end_lap": int(lap["LapNumber"]),
                "laps": 1,
            }
        else:
            current_stint["end_lap"] = int(lap["LapNumber"])
            current_stint["laps"] += 1

    if current_stint is not None:
        stints.append(current_stint)

    lap_times = []
    for _, lap in driver_laps.iterrows():
        if pd.notna(lap["LapTime"]):
            lap_times.append({
                "lap": int(lap["LapNumber"]),
                "time_sec": float(lap["LapTime"].total_seconds()),
                "compound": str(lap.get("Compound", "UNKNOWN")),
                "tyre_life": int(lap.get("TyreLife", 0)),
            })

    total_time = sum(lt["time_sec"] for lt in lap_times) if lap_times else 0

    pit_laps = []
    for i in range(len(stints) - 1):
        pit_laps.append({
            "lap": stints[i]["end_lap"],
            "from_compound": stints[i]["compound"],
            "to_compound": stints[i + 1]["compound"],
        })

    return {
        "stints": stints,
        "lap_times": lap_times,
        "total_time": float(total_time),
        "pit_laps": pit_laps,
        "total_laps": int(driver_laps["LapNumber"].max()),
    }


def estimate_lap_time(models: dict, compound: str, tyre_life: int, race_lap: int = None, total_race_laps: int = None) -> float:
    """Estimate lap time for a given compound and tire age.
    
    If race_lap and total_race_laps are provided, includes fuel effect.
    """
    if compound not in models:
        if models:
            avg_base = np.mean([m["base_time"] for m in models.values()])
            avg_deg = np.mean([m["deg_rate"] for m in models.values()])
            base_time = float(avg_base + avg_deg * tyre_life)
        else:
            base_time = 90.0
    else:
        model = models[compound]
        base_time = float(model["base_time"] + model["deg_rate"] * tyre_life)
    
    # Apply fuel effect: earlier laps are slower due to fuel weight
    if race_lap is not None and total_race_laps is not None:
        # Cars are heavier at start, lighter at end
        # Penalty is relative to end of race (when car is lightest)
        fuel_penalty = (total_race_laps - race_lap) * FUEL_EFFECT_PER_LAP
        base_time += fuel_penalty
    
    return base_time


def analyze_stints(
    models: dict,
    user_stints: list[dict],
    actual: dict | None,
    pit_loss: float,
    total_race_laps: int,
) -> list[dict]:
    """Per-stint analysis comparing user strategy to actual."""
    if not actual or not actual.get("lap_times"):
        return []

    actual_by_lap = {lt["lap"]: lt for lt in actual["lap_times"]}
    results = []
    current_lap = 1

    for stint_idx, stint in enumerate(user_stints):
        compound = stint["compound"]
        num_laps = stint["laps"]
        end_lap = current_lap + num_laps - 1

        # Sum user time for this stint
        user_time = 0.0
        for lap_in_stint in range(num_laps):
            tyre_life = lap_in_stint + 1
            lap_time = estimate_lap_time(models, compound, tyre_life,
                                         race_lap=current_lap + lap_in_stint,
                                         total_race_laps=total_race_laps)
            is_pit = lap_in_stint == num_laps - 1 and stint_idx < len(user_stints) - 1
            if is_pit:
                lap_time += pit_loss
            user_time += lap_time

        # Sum actual time over same lap range
        actual_time = 0.0
        actual_count = 0
        for lap in range(current_lap, end_lap + 1):
            if lap in actual_by_lap:
                actual_time += actual_by_lap[lap]["time_sec"]
                actual_count += 1

        if actual_count == 0:
            current_lap = end_lap + 1
            continue

        delta = user_time - actual_time

        # Generate explanation
        explanation = _explain_stint(
            models, compound, num_laps, delta, actual, current_lap, end_lap, stint_idx, user_stints
        )

        results.append({
            "stint": stint_idx + 1,
            "compound": compound,
            "laps": num_laps,
            "delta": round(delta, 3),
            "explanation": explanation,
        })
        current_lap = end_lap + 1

    return results


def _explain_stint(
    models: dict, compound: str, num_laps: int, delta: float,
    actual: dict, start_lap: int, end_lap: int, stint_idx: int, user_stints: list[dict]
) -> str:
    """Generate a human-readable explanation for a stint delta."""
    abs_delta = abs(delta)

    # Check if this stint is long enough to hit tire cliff
    model = models.get(compound, {})
    deg_rate = model.get("deg_rate", 0.04)
    late_deg = deg_rate * num_laps  # degradation at end of stint
    cliff = late_deg > 1.5  # More than 1.5s slower at end = cliff territory

    # Check actual compound usage in this lap range
    actual_compounds = set()
    for lt in actual.get("lap_times", []):
        if start_lap <= lt["lap"] <= end_lap:
            actual_compounds.add(lt["compound"])

    # Find actual pit laps near this stint boundary
    actual_pits = [p["lap"] for p in actual.get("pit_laps", [])]
    pit_timing_diff = None
    if stint_idx < len(user_stints) - 1:
        user_pit_lap = end_lap
        closest = min(actual_pits, key=lambda p: abs(p - user_pit_lap), default=None)
        if closest is not None:
            pit_timing_diff = user_pit_lap - closest

    if abs_delta < 1.0:
        return "Similar pace to actual — well matched."
    elif cliff and delta > 0:
        return f"Tire cliff: {compound} degrades {late_deg:.1f}s by lap {num_laps}. Consider pitting earlier."
    elif pit_timing_diff is not None and abs(pit_timing_diff) > 5 and delta > 0:
        direction = "later" if pit_timing_diff > 0 else "earlier"
        return f"Pitted {abs(pit_timing_diff)} laps {direction} than actual — stint too {'long' if pit_timing_diff > 0 else 'short'} on {compound}."
    elif len(actual_compounds) == 1 and compound not in actual_compounds:
        actual_c = next(iter(actual_compounds))
        if delta > 0:
            return f"Used {compound} where actual used {actual_c} — lost {abs_delta:.1f}s. {actual_c} may suit this phase better."
        else:
            return f"Used {compound} where actual used {actual_c} — gained {abs_delta:.1f}s. Good compound choice!"
    elif delta > 0:
        return f"Lost {abs_delta:.1f}s vs actual over this stint."
    else:
        return f"Gained {abs_delta:.1f}s vs actual — strong stint!"


def find_optimal_strategies(
    models: dict, pit_loss: float, total_race_laps: int
) -> list[dict]:
    """Brute-force search for best 1-stop, 2-stop, and 3-stop strategies."""
    compounds = ["SOFT", "MEDIUM", "HARD"]
    best = {}  # key: num_stops, value: (time, stints)

    n = total_race_laps
    min_stint = 5

    # 1-stop strategies
    for pit1 in range(min_stint, n - min_stint + 1, 2):
        for c1 in compounds:
            for c2 in compounds:
                if c1 == c2:
                    continue
                stints = [{"compound": c1, "laps": pit1}, {"compound": c2, "laps": n - pit1}]
                laps = simulate_strategy(models, stints, pit_loss, n)
                total = sum(l["time_sec"] for l in laps)
                if 1 not in best or total < best[1][0]:
                    best[1] = (total, stints)

    # 2-stop strategies
    for pit1 in range(min_stint, n - 2 * min_stint + 1, 3):
        for pit2 in range(pit1 + min_stint, n - min_stint + 1, 3):
            for c1 in compounds:
                for c2 in compounds:
                    for c3 in compounds:
                        if len({c1, c2, c3}) < 2:
                            continue
                        stints = [
                            {"compound": c1, "laps": pit1},
                            {"compound": c2, "laps": pit2 - pit1},
                            {"compound": c3, "laps": n - pit2},
                        ]
                        laps = simulate_strategy(models, stints, pit_loss, n)
                        total = sum(l["time_sec"] for l in laps)
                        if 2 not in best or total < best[2][0]:
                            best[2] = (total, stints)

    # 3-stop strategies
    for pit1 in range(min_stint, n - 3 * min_stint + 1, 5):
        for pit2 in range(pit1 + min_stint, n - 2 * min_stint + 1, 5):
            for pit3 in range(pit2 + min_stint, n - min_stint + 1, 5):
                for c1 in compounds:
                    for c2 in compounds:
                        for c3 in compounds:
                            for c4 in compounds:
                                if len({c1, c2, c3, c4}) < 2:
                                    continue
                                stints = [
                                    {"compound": c1, "laps": pit1},
                                    {"compound": c2, "laps": pit2 - pit1},
                                    {"compound": c3, "laps": pit3 - pit2},
                                    {"compound": c4, "laps": n - pit3},
                                ]
                                laps = simulate_strategy(models, stints, pit_loss, n)
                                total = sum(l["time_sec"] for l in laps)
                                if 3 not in best or total < best[3][0]:
                                    best[3] = (total, stints)

    return best


def simulate_strategy(models: dict, stints: list[dict], pit_loss: float, total_race_laps: int) -> list[dict]:
    """Simulate a strategy and return estimated lap times."""
    results = []
    current_lap = 1

    for stint_idx, stint in enumerate(stints):
        compound = stint["compound"]
        num_laps = stint["laps"]

        for lap_in_stint in range(num_laps):
            tyre_life = lap_in_stint + 1
            lap_time = estimate_lap_time(
                models, compound, tyre_life, 
                race_lap=current_lap, 
                total_race_laps=total_race_laps
            )

            is_pit_lap = lap_in_stint == num_laps - 1 and stint_idx < len(stints) - 1
            if is_pit_lap:
                lap_time += pit_loss

            results.append({
                "lap": current_lap,
                "time_sec": float(lap_time),
                "compound": compound,
                "tyre_life": tyre_life,
                "is_pit_lap": is_pit_lap,
            })
            current_lap += 1

    return results
