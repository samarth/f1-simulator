import numpy as np
import plotly.express as px

from .session_service import load_session
from ..utils.formatting import format_lap_time


DRIVER_COLORS = px.colors.qualitative.Set1


def get_telemetry(year: int, race: str, session_type: str, drivers: list[str]) -> dict:
    """Get telemetry data for selected drivers, pre-interpolated."""
    session = load_session(year, race, session_type)
    laps = session.laps

    fastest_lap = laps.pick_fastest()
    session_info = {
        "fastest_driver": str(fastest_lap["Driver"]),
        "fastest_time": format_lap_time(fastest_lap["LapTime"]),
        "fastest_lap_number": int(fastest_lap["LapNumber"]),
    }

    driver_data = []
    speed_traces: dict[str, np.ndarray] = {}
    common_distance = None

    for i, driver in enumerate(drivers):
        driver_laps = laps[laps["Driver"] == driver]
        if driver_laps.empty:
            continue

        driver_fastest = driver_laps.pick_fastest()
        telemetry = driver_fastest.get_telemetry()
        color = DRIVER_COLORS[i % len(DRIVER_COLORS)]

        # Subsample track data to ~500 points
        total_points = len(telemetry)
        step = max(1, total_points // 500)
        track_sub = telemetry.iloc[::step]

        track_points = [
            {"x": float(row["X"]), "y": float(row["Y"]), "speed": float(row["Speed"])}
            for _, row in track_sub.iterrows()
        ]

        # Speed data - interpolate to 200 common points
        distance = telemetry["Distance"].values
        speed = telemetry["Speed"].values

        if common_distance is None:
            common_distance = np.linspace(float(distance.min()), float(distance.max()), 200)

        speed_interp = np.interp(common_distance, distance, speed)
        speed_traces[driver] = speed_interp

        speed_points = [
            {"distance": float(d), "speed": float(s)}
            for d, s in zip(common_distance, speed_interp)
        ]

        driver_data.append({
            "driver": driver,
            "lap_time": format_lap_time(driver_fastest["LapTime"]),
            "lap_number": int(driver_fastest["LapNumber"]),
            "color": color,
            "track": track_points,
            "speed": speed_points,
        })

    # Build speed comparison array
    speed_comparison = []
    if common_distance is not None:
        for idx, d in enumerate(common_distance):
            point = {"distance": float(d), "speeds": {}}
            for drv, speeds in speed_traces.items():
                point["speeds"][drv] = float(speeds[idx])
            speed_comparison.append(point)

    return {
        "session_info": session_info,
        "drivers": driver_data,
        "speed_comparison": speed_comparison,
    }
