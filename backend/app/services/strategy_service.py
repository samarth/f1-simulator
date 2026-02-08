import numpy as np
import pandas as pd

from .session_service import load_session


def get_race_degradation_data(session) -> dict:
    """Extract tire degradation curves from a race session."""
    laps = session.laps
    degradation = {}

    for compound in ["SOFT", "MEDIUM", "HARD"]:
        try:
            compound_laps = laps.pick_tyre(compound)
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


def build_degradation_model(degradation_data: dict) -> dict:
    """Build linear degradation models from data."""
    models = {}
    for compound, data in degradation_data.items():
        tyre_life = np.array(data["tyre_life"])
        avg_times = np.array(data["avg_lap_time"])

        if len(tyre_life) < 2:
            models[compound] = {
                "base_time": float(avg_times[0]) if len(avg_times) > 0 else 90.0,
                "deg_rate": 0.05,
            }
        else:
            coeffs = np.polyfit(tyre_life, avg_times, 1)
            models[compound] = {
                "base_time": float(coeffs[1]),
                "deg_rate": float(coeffs[0]),
            }

    return models


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


def estimate_lap_time(models: dict, compound: str, tyre_life: int) -> float:
    """Estimate lap time for a given compound and tire age."""
    if compound not in models:
        if models:
            avg_base = np.mean([m["base_time"] for m in models.values()])
            avg_deg = np.mean([m["deg_rate"] for m in models.values()])
            return float(avg_base + avg_deg * tyre_life)
        return 90.0

    model = models[compound]
    return float(model["base_time"] + model["deg_rate"] * tyre_life)


def simulate_strategy(models: dict, stints: list[dict], pit_loss: float, total_race_laps: int) -> list[dict]:
    """Simulate a strategy and return estimated lap times."""
    results = []
    current_lap = 1

    for stint_idx, stint in enumerate(stints):
        compound = stint["compound"]
        num_laps = stint["laps"]

        for lap_in_stint in range(num_laps):
            tyre_life = lap_in_stint + 1
            lap_time = estimate_lap_time(models, compound, tyre_life)

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
