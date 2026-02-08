from fastapi import APIRouter, Query

from ..services.race_service import get_drivers

router = APIRouter()


@router.get("/api/drivers")
def list_drivers(
    year: int = Query(...),
    race: str = Query(...),
    session: str = Query("R"),
):
    drivers = get_drivers(year, race, session)
    return {"drivers": drivers}
