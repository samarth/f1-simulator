from fastapi import APIRouter, HTTPException

from ..models.strategy import SimulateRequest
from ..services.session_service import load_session
from ..services.strategy_service import (
    build_degradation_model,
    get_pit_stop_stats,
    get_driver_actual_strategy,
    simulate_strategy,
    analyze_stints,
    find_optimal_strategies,
)

router = APIRouter()


@router.post("/api/simulate")
def run_simulation(req: SimulateRequest):
    session = load_session(req.year, req.race, "R")
    laps = session.laps
    total_race_laps = int(laps["LapNumber"].max())

    total_planned = sum(s.laps for s in req.stints)
    if total_planned != total_race_laps:
        raise HTTPException(
            status_code=400,
            detail=f"Total planned laps ({total_planned}) must equal race distance ({total_race_laps}).",
        )

    unique_compounds = set(s.compound for s in req.stints)
    if len(unique_compounds) < 2:
        raise HTTPException(status_code=400, detail="Must use at least 2 different tire compounds.")

    models = build_degradation_model(session)
    pit_stats = get_pit_stop_stats(session)
    pit_loss = pit_stats["avg_pit_time"]

    stints_dicts = [{"compound": s.compound, "laps": s.laps} for s in req.stints]
    sim_results = simulate_strategy(models, stints_dicts, pit_loss, total_race_laps)

    actual = get_driver_actual_strategy(session, req.driver)

    user_total = sum(r["time_sec"] for r in sim_results)

    # Compute cumulative gap
    cumulative_gap = []
    if actual and actual["lap_times"]:
        actual_dict = {lt["lap"]: lt["time_sec"] for lt in actual["lap_times"]}
        user_dict = {r["lap"]: r["time_sec"] for r in sim_results}
        common_laps = sorted(set(actual_dict.keys()) & set(user_dict.keys()))
        running_diff = 0.0
        for lap in common_laps:
            running_diff += user_dict[lap] - actual_dict[lap]
            cumulative_gap.append({"lap": lap, "gap": round(running_diff, 3)})

    # Per-stint analysis
    stint_analysis = analyze_stints(models, stints_dicts, actual, pit_loss, total_race_laps)

    # Find optimal strategies
    optimal = find_optimal_strategies(models, pit_loss, total_race_laps)
    actual_total = actual["total_time"] if actual else user_total
    suggested = []
    labels = {1: "Best 1-stop", 2: "Best 2-stop", 3: "Best 3-stop"}
    for num_stops in sorted(optimal.keys()):
        total_time, opt_stints = optimal[num_stops]
        suggested.append({
            "label": labels.get(num_stops, f"Best {num_stops}-stop"),
            "stints": [{"compound": s["compound"], "laps": s["laps"]} for s in opt_stints],
            "total_time": round(total_time, 3),
            "delta_vs_actual": round(total_time - actual_total, 3),
        })

    return {
        "simulated_laps": sim_results,
        "user_total_time": user_total,
        "actual": actual,
        "cumulative_gap": cumulative_gap,
        "stint_analysis": stint_analysis,
        "suggested_strategies": suggested,
    }
