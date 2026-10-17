from fastapi import APIRouter, Query

from ..services.race_service import get_races, get_years

router = APIRouter()


@router.get("/api/years")
def list_years():
    return {"years": get_years()}


@router.get("/api/races")
def list_races(year: int = Query(...)):
    races = get_races(year)
    return {"year": year, "races": races}
