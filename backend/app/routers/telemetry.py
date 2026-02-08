from fastapi import APIRouter, Query

from ..services.telemetry_service import get_telemetry

router = APIRouter()


@router.get("/api/telemetry")
def fetch_telemetry(
    year: int = Query(...),
    race: str = Query(...),
    session: str = Query("R"),
    drivers: str = Query(..., description="Comma-separated driver codes"),
):
    driver_list = [d.strip() for d in drivers.split(",") if d.strip()]
    data = get_telemetry(year, race, session, driver_list)
    return data
