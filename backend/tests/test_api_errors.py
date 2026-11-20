"""HTTP errors for session and driver selection."""

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.openf1_client import OpenF1Error
from app.services.race_service import get_drivers

client = TestClient(app)


def test_non_race_session_is_rejected_before_any_fetch():
    try:
        get_drivers(2024, "Bahrain Grand Prix", "Q")
    except OpenF1Error as exc:
        assert exc.status_code == 400
        assert "race" in exc.message.lower()
    else:
        raise AssertionError("qualifying should be rejected")

    response = client.get(
        "/api/drivers",
        params={"year": 2024, "race": "Bahrain Grand Prix", "session": "Q"},
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "error" not in body


def _empty_race():
    class FakeRace:
        laps = pd.DataFrame(
            columns=[
                "Driver",
                "LapNumber",
                "LapTime",
                "Compound",
                "TyreLife",
                "Stint",
                "IsPitOut",
                "IsPitIn",
                "PitDuration",
            ]
        )
        weather_data = pd.DataFrame()

    return FakeRace()


def test_unknown_driver_is_404_not_an_error_object(monkeypatch):
    fake = _empty_race()
    monkeypatch.setattr("app.routers.strategy.load_race", lambda year, race: fake)
    monkeypatch.setattr("app.routers.simulate.load_race", lambda year, race: fake)

    actual = client.get(
        "/api/actual-strategy",
        params={"year": 2024, "race": "Bahrain Grand Prix", "driver": "ZZZ"},
    )
    assert actual.status_code == 404
    assert actual.json()["detail"]
    assert "error" not in actual.json()

    simulated = client.post(
        "/api/simulate",
        json={"year": 2024, "race": "Bahrain Grand Prix", "driver": "ZZZ", "stints": []},
    )
    assert simulated.status_code == 404
    assert "error" not in simulated.json()
    assert "detail" in simulated.json()
