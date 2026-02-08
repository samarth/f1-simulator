from fastapi import APIRouter, Query

from ..services.race_service import get_races

router = APIRouter()


@router.get("/api/races")
def list_races(year: int = Query(...)):
    races = get_races(year)
    return {"year": year, "races": races}
