from fastapi import APIRouter, Query

from ..services.openf1_client import OpenF1Error

from ..services.race_service import load_race
from ..services.strategy_service import (
    build_race_model,
    get_pit_stop_stats,
    get_driver_actual_strategy,
    get_weather_data,
    get_fuel_effect_data,
    model_info,
    replay_driver,
)
from ..services.strategy_math import degradation_series

router = APIRouter()


@router.get("/api/degradation")
def fetch_degradation(year: int = Query(...), race: str = Query(...)):
    """Get tire degradation curves with fuel correction, weather, and fuel effect data."""
    session = load_race(year, race)
    race_model = build_race_model(session)
    total_laps = race_model["total_laps"] or 0
    return {
        "compounds": degradation_series(
            race_model["rows"],
            race_model["models"],
            race_model["neutral"],
            race_model["fuel_per_lap"],
        ),
        "models": race_model["models"],
        "weather": get_weather_data(session),
        "fuel_effect": get_fuel_effect_data(total_laps, race_model),
        "total_laps": total_laps,
        "model_info": model_info(race_model),
    }


@router.get("/api/pit-stats")
def fetch_pit_stats(year: int = Query(...), race: str = Query(...)):
    session = load_race(year, race)
    return get_pit_stop_stats(session)


@router.get("/api/actual-strategy")
def fetch_actual_strategy(
    year: int = Query(...),
    race: str = Query(...),
    driver: str = Query(...),
):
    session = load_race(year, race)
    result = get_driver_actual_strategy(session, driver)
    if result is None:
        raise OpenF1Error(f"No lap data for {driver} at {race} ({year}).", 404)
    result["model_fit"] = replay_driver(session, driver, result)
    return result
