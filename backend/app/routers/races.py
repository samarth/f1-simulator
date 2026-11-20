from fastapi import APIRouter, Query

from ..services.race_service import get_races, get_years, latest_available_race

router = APIRouter()


@router.get("/api/years")
def list_years():
    default = latest_available_race()
    return {
        "years": get_years(),
        "default_year": None if default is None else default.year,
        "default_race": None if default is None else default.name,
    }


@router.get("/api/races")
def list_races(year: int = Query(...)):
    races = get_races(year)
    return {"year": year, "races": races}
