from pydantic import BaseModel


class CompoundDegradation(BaseModel):
    tyre_life: list[int]
    avg_lap_time: list[float]
    std_lap_time: list[float]
    count: list[int]


class DegradationModel(BaseModel):
    base_time: float
    deg_rate: float


class DegradationResponse(BaseModel):
    compounds: dict[str, CompoundDegradation]
    models: dict[str, DegradationModel]


class PitStatsResponse(BaseModel):
    avg_pit_time: float
    min_pit_time: float
    max_pit_time: float
    num_stops: int


class StintInfo(BaseModel):
    stint: int
    compound: str
    start_lap: int
    end_lap: int
    laps: int


class LapTime(BaseModel):
    lap: int
    time_sec: float
    compound: str
    tyre_life: int


class PitLap(BaseModel):
    lap: int
    from_compound: str
    to_compound: str


class ActualStrategyResponse(BaseModel):
    stints: list[StintInfo]
    lap_times: list[LapTime]
    total_time: float
    pit_laps: list[PitLap]
    total_laps: int


class StintInput(BaseModel):
    compound: str
    laps: int


class SimulateRequest(BaseModel):
    year: int
    race: str
    driver: str
    stints: list[StintInput]


class SimulatedLap(BaseModel):
    lap: int
    time_sec: float
    compound: str
    tyre_life: int
    is_pit_lap: bool


class CumulativeGapPoint(BaseModel):
    lap: int
    gap: float


class StintAnalysis(BaseModel):
    stint: int
    compound: str
    laps: int
    delta: float
    explanation: str


class SuggestedStrategy(BaseModel):
    label: str
    stints: list[StintInput]
    total_time: float
    delta_vs_actual: float


class SimulateResponse(BaseModel):
    simulated_laps: list[SimulatedLap]
    user_total_time: float
    actual: ActualStrategyResponse | None
    cumulative_gap: list[CumulativeGapPoint]
    stint_analysis: list[StintAnalysis]
    suggested_strategies: list[SuggestedStrategy]
