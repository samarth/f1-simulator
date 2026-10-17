from fastapi import APIRouter, Query

from ..services.openf1_client import OpenF1Error

from ..services.race_service import load_race
from ..services.strategy_service import (
    get_race_degradation_data,
    build_degradation_model,
    get_pit_stop_stats,
    get_driver_actual_strategy,
    get_weather_data,
    get_fuel_effect_data,
)

router = APIRouter()


@router.get("/api/degradation")
def fetch_degradation(year: int = Query(...), race: str = Query(...)):
    """Get tire degradation curves with fuel correction, weather, and fuel effect data."""
    session = load_race(year, race)
    
    # Get total race laps for fuel calculation
    total_laps = int(session.laps["LapNumber"].max()) if not session.laps.empty else 57
    
    # Get degradation data for visualization (raw data grouped by tyre life)
    deg_data = get_race_degradation_data(session, fuel_corrected=False)
    
    # Get per-stint degradation models (more accurate, avoids fuel confounding)
    models = build_degradation_model(session)
    
    # Get weather and fuel info
    weather = get_weather_data(session)
    fuel_effect = get_fuel_effect_data(total_laps)
    
    return {
        "compounds": deg_data,
        "models": models,
        "weather": weather,
        "fuel_effect": fuel_effect,
        "total_laps": total_laps,
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
    return result
