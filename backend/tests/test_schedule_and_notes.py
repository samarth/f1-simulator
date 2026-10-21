"""Defaults, weather samples, and compounds the model leaves out."""

from datetime import date

import pandas as pd

from app.main import app
from app.services.openf1_client import OpenF1Error
from app.services.race_service import RaceEvent, latest_available_race
from app.services.strategy_service import get_weather_data, left_out_note
from fastapi.testclient import TestClient

client = TestClient(app)


def test_latest_race_skips_future_meetings_and_unpublished_drivers(monkeypatch):
    events = [
        RaceEvent(2027, 1, "Bahrain Grand Prix", "Bahrain", "2027-03-14", 1, 11),
        RaceEvent(2026, 18, "United States Grand Prix", "USA", "2026-10-18", 3, 33),
        RaceEvent(2026, 17, "Singapore Grand Prix", "Singapore", "2026-10-11", 2, 22),
    ]
    monkeypatch.setattr("app.services.race_service.list_events", lambda: events)

    def drivers(year, race, session_type="R"):
        if race == "Singapore Grand Prix":
            return [{"code": "VER", "name": "Verstappen", "team": "Red Bull"}]
        raise OpenF1Error("no driver list", 404)

    monkeypatch.setattr("app.services.race_service.get_drivers", drivers)
    chosen = latest_available_race(date(2026, 10, 21))
    assert chosen is not None
    assert chosen.name == "Singapore Grand Prix"
    assert chosen.year == 2026


def test_years_payload_includes_the_default_race(monkeypatch):
    monkeypatch.setattr("app.routers.races.get_years", lambda: [2027, 2026, 2025])
    monkeypatch.setattr(
        "app.routers.races.latest_available_race",
        lambda: RaceEvent(2026, 17, "Singapore Grand Prix", "Singapore", "2026-10-11", 2, 22),
    )
    response = client.get("/api/years")
    assert response.status_code == 200
    body = response.json()
    assert body["default_year"] == 2026
    assert body["default_race"] == "Singapore Grand Prix"
    assert body["years"][0] == 2027


def test_zero_track_temperature_is_dropped():
    class Session:
        weather_data = pd.DataFrame(
            {
                "AirTemp": [30.2, 30.2, 30.3],
                "TrackTemp": [0.0, 41.2, 45.3],
                "Humidity": [69.0, 70.0, 72.0],
                "Rainfall": [0, 0, 0],
                "WindSpeed": [1.0, 1.2, 1.1],
            }
        )

    weather = get_weather_data(Session())
    assert weather["track_temp_min"] == 41.2
    assert weather["track_temp_max"] == 45.3
    assert weather["track_temp"] == 43.2


def test_dry_race_names_a_compound_with_no_clean_laps():
    note = left_out_note(
        {
            "wet": False,
            "models": {"SOFT": {}, "HARD": {}},
            "unmodeled": [],
        }
    )
    assert note == "MEDIUM is left out because there are not enough clean laps to fit it."
    assert left_out_note({"wet": False, "models": {"SOFT": {}, "MEDIUM": {}, "HARD": {}}, "unmodeled": []}) == ""
