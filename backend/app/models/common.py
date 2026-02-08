from pydantic import BaseModel


class RaceInfo(BaseModel):
    round: int
    name: str
    country: str
    date: str


class RacesResponse(BaseModel):
    year: int
    races: list[RaceInfo]


class DriverInfo(BaseModel):
    code: str
    name: str
    team: str


class DriversResponse(BaseModel):
    drivers: list[DriverInfo]
