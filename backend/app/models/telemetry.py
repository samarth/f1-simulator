from pydantic import BaseModel


class TrackPoint(BaseModel):
    x: float
    y: float
    speed: float


class SpeedPoint(BaseModel):
    distance: float
    speed: float


class DriverTelemetry(BaseModel):
    driver: str
    lap_time: str
    lap_number: int
    color: str
    track: list[TrackPoint]
    speed: list[SpeedPoint]


class SpeedComparisonPoint(BaseModel):
    distance: float
    speeds: dict[str, float]


class SessionInfo(BaseModel):
    fastest_driver: str
    fastest_time: str
    fastest_lap_number: int


class TelemetryResponse(BaseModel):
    session_info: SessionInfo
    drivers: list[DriverTelemetry]
    speed_comparison: list[SpeedComparisonPoint]
