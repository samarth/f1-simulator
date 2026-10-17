from fastapi import APIRouter, HTTPException

from ..models.strategy import SimulateRequest
from ..services.openf1_client import OpenF1Error
from ..services.race_service import load_race
from ..services.strategy_service import (
    build_race_model,
    driver_context,
    get_driver_actual_strategy,
    simulate_strategy,
    analyze_stints,
    find_optimal_strategies,
    replay_driver,
    user_plan_problem,
)
from ..services.strategy_math import compared_total

router = APIRouter()


@router.post("/api/simulate")
def run_simulation(req: SimulateRequest):
    session = load_race(req.year, req.race)
    race_model = build_race_model(session)
    total_race_laps = race_model["total_laps"]

    total_planned = sum(s.laps for s in req.stints)
    if total_planned != total_race_laps:
        raise HTTPException(
            status_code=400,
            detail=f"Total planned laps ({total_planned}) must equal race distance ({total_race_laps}).",
        )

    stints_dicts = [{"compound": s.compound, "laps": s.laps} for s in req.stints]
    problem = user_plan_problem(stints_dicts, race_model["observed"], race_model["wet"])
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    actual = get_driver_actual_strategy(session, req.driver)
    if actual is None:
        raise OpenF1Error(
            f"No lap data for {req.driver} at {req.race} ({req.year}).",
            404,
        )

    context = driver_context(race_model, req.driver)
    sim_results = simulate_strategy(
        race_model["models"],
        stints_dicts,
        context["pit_loss"],
        total_race_laps,
        race_model["fuel_per_lap"],
        context["driver_offset"],
        context["neutral_times"],
        race_model.get("field_pace") or None,
    )
    actual_by_lap = {lt["lap"]: lt["time_sec"] for lt in actual["lap_times"]}
    user_total = compared_total(sim_results, actual_by_lap)

    cumulative_gap = []
    running_diff = 0.0
    for lap in sim_results:
        if lap["lap"] not in actual_by_lap:
            continue
        running_diff += lap["time_sec"] - actual_by_lap[lap["lap"]]
        cumulative_gap.append({"lap": lap["lap"], "gap": round(running_diff, 3)})

    stint_analysis = analyze_stints(
        race_model["models"],
        stints_dicts,
        actual,
        context["pit_loss"],
        total_race_laps,
        race_model["fuel_per_lap"],
        context["driver_offset"],
        context["neutral_times"],
        race_model.get("field_pace") or None,
    )

    optimal = find_optimal_strategies(
        race_model["models"],
        context["pit_loss"],
        total_race_laps,
        race_model["fuel_per_lap"],
        context["driver_offset"],
        context["neutral_times"],
        race_model["wet"],
        race_model["windows"],
        race_model["mixed"],
        race_model.get("field_pace") or None,
        race_model["max_stint"],
    )
    actual_total = actual["total_time"]
    suggested = []
    labels = {1: "Best 1-stop", 2: "Best 2-stop", 3: "Best 3-stop"}
    for num_stops in sorted(optimal.keys()):
        _total, opt_stints = optimal[num_stops]
        projected = simulate_strategy(
            race_model["models"],
            opt_stints,
            context["pit_loss"],
            total_race_laps,
            race_model["fuel_per_lap"],
            context["driver_offset"],
            context["neutral_times"],
            race_model.get("field_pace") or None,
        )
        total_time = compared_total(projected, actual_by_lap)
        suggested.append({
            "label": labels.get(num_stops, f"Best {num_stops}-stop"),
            "stints": [{"compound": s["compound"], "laps": s["laps"]} for s in opt_stints],
            "total_time": round(total_time, 3),
            "delta_vs_actual": round(total_time - actual_total, 3),
        })

    fit = replay_driver(session, req.driver, actual)
    return {
        "simulated_laps": sim_results,
        "user_total_time": user_total,
        "actual": actual,
        "cumulative_gap": cumulative_gap,
        "stint_analysis": stint_analysis,
        "suggested_strategies": suggested,
        "model_fit": fit,
    }
