from fastapi import APIRouter, Query

from ..services.session_service import load_session
from ..services.strategy_service import (
    get_race_degradation_data,
    build_degradation_model,
    get_pit_stop_stats,
    get_driver_actual_strategy,
)

router = APIRouter()


@router.get("/api/degradation")
def fetch_degradation(year: int = Query(...), race: str = Query(...)):
    session = load_session(year, race, "R")
    deg_data = get_race_degradation_data(session)
    models = build_degradation_model(deg_data)
    return {"compounds": deg_data, "models": models}


@router.get("/api/pit-stats")
def fetch_pit_stats(year: int = Query(...), race: str = Query(...)):
    session = load_session(year, race, "R")
    return get_pit_stop_stats(session)


@router.get("/api/actual-strategy")
def fetch_actual_strategy(
    year: int = Query(...),
    race: str = Query(...),
    driver: str = Query(...),
):
    session = load_session(year, race, "R")
    result = get_driver_actual_strategy(session, driver)
    if result is None:
        return {"error": "No data found for driver"}
    return result
