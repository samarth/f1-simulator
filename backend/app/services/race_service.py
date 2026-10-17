"""Race schedule, drivers, and lap tables loaded from OpenF1."""

from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

import pandas as pd

from .openf1_client import OpenF1Error, client

RACE_CACHE_TTL_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class RaceEvent:
    year: int
    round: int
    name: str
    country: str
    date: str
    meeting_key: int
    session_key: int


@dataclass
class LoadedRace:
    """Lap and weather tables in the shape the strategy engine already uses."""

    year: int
    name: str
    session_key: int
    laps: pd.DataFrame
    weather_data: pd.DataFrame


_race_lock = threading.Lock()
_race_cache: dict[int, tuple[float, LoadedRace]] = {}


def get_years() -> list[int]:
    years = {event.year for event in list_events()}
    return sorted(years, reverse=True)


def get_races(year: int) -> list[dict]:
    races = [event for event in list_events() if event.year == year]
    return [
        {
            "round": event.round,
            "name": event.name,
            "country": event.country,
            "date": event.date,
        }
        for event in races
    ]


def get_drivers(year: int, race: str, session_type: str = "R") -> list[dict]:
    if session_type not in {"R", "Race", "race"}:
        raise OpenF1Error("Only race sessions are available in this simulator.", 400)
    event = find_event(year, race)
    rows = client.get_json("drivers", {"session_key": event.session_key})
    if not rows:
        raise OpenF1Error(
            f"OpenF1 has no driver list for {race} ({year}). The session may not have been published yet.",
            404,
        )
    drivers = []
    for row in rows:
        code = row.get("name_acronym") or str(row.get("driver_number") or "")
        if not code:
            continue
        name = row.get("full_name") or row.get("broadcast_name") or code
        team = row.get("team_name") or ""
        drivers.append({"code": str(code), "name": str(name), "team": str(team)})
    drivers.sort(key=lambda driver: driver["code"])
    if not drivers:
        raise OpenF1Error(f"OpenF1 has no driver list for {race} ({year}).", 404)
    return drivers


def load_race(year: int, race: str) -> LoadedRace:
    event = find_event(year, race)
    now = time.monotonic()
    with _race_lock:
        cached = _race_cache.get(event.session_key)
        if cached is not None and cached[0] > now:
            loaded = cached[1]
            return LoadedRace(year, race, loaded.session_key, loaded.laps, loaded.weather_data)

    loaded = _fetch_race(event, race)
    with _race_lock:
        _race_cache[event.session_key] = (time.monotonic() + RACE_CACHE_TTL_SECONDS, loaded)
    return loaded


def find_event(year: int, race: str) -> RaceEvent:
    matches = [event for event in list_events() if event.year == year and event.name == race]
    if not matches:
        raise OpenF1Error(f"No {year} race named \"{race}\" in the OpenF1 schedule.", 404)
    return matches[0]


def list_events() -> list[RaceEvent]:
    meetings = {
        row["meeting_key"]: row
        for row in client.get_json("meetings", schedule=True)
        if row.get("meeting_key") is not None
    }
    sessions = client.get_json("sessions", {"session_name": "Race"}, schedule=True)

    grouped: dict[int, list[dict]] = defaultdict(list)
    for session in sessions:
        if session.get("is_cancelled") or session.get("session_key") is None:
            continue
        meeting = meetings.get(session.get("meeting_key")) or {}
        if meeting.get("is_cancelled"):
            continue
        year = session.get("year") or meeting.get("year")
        if year is None:
            continue
        base_name = meeting.get("meeting_name") or f"{session.get('country_name') or 'Unknown'} Grand Prix"
        date = str(session.get("date_start") or meeting.get("date_start") or "")[:10]
        country = meeting.get("country_name") or session.get("country_name") or ""
        grouped[int(year)].append(
            {
                "base_name": str(base_name),
                "date": date,
                "country": str(country),
                "meeting_key": int(session.get("meeting_key") or 0),
                "session_key": int(session["session_key"]),
            }
        )

    events: list[RaceEvent] = []
    for year in sorted(grouped):
        items = sorted(grouped[year], key=lambda item: (item["date"], item["session_key"]))
        counts = Counter(item["base_name"] for item in items)
        used: dict[str, int] = {}
        for index, item in enumerate(items, start=1):
            name = item["base_name"]
            if counts[name] > 1 and item["date"]:
                name = f"{name} ({item['date']})"
            if name in used:
                name = f"{name} #{item['session_key']}"
            used[name] = item["session_key"]
            events.append(
                RaceEvent(
                    year=year,
                    round=index,
                    name=name,
                    country=item["country"],
                    date=item["date"],
                    meeting_key=item["meeting_key"],
                    session_key=item["session_key"],
                )
            )
    return events


def _fetch_race(event: RaceEvent, race_name: str) -> LoadedRace:
    params = {"session_key": event.session_key}
    lap_rows = client.get_json("laps", params)
    stint_rows = client.get_json("stints", params)
    pit_rows = client.get_json("pit", params)
    driver_rows = client.get_json("drivers", params)
    weather_rows = client.get_json("weather", params)

    laps = _build_laps(lap_rows, stint_rows, pit_rows, driver_rows)
    if laps.empty or not laps["LapTime"].notna().any():
        raise OpenF1Error(
            f"OpenF1 has no lap times for {race_name} ({event.year}). "
            "The session may not have been run yet.",
            404,
        )
    return LoadedRace(
        year=event.year,
        name=race_name,
        session_key=event.session_key,
        laps=laps,
        weather_data=_build_weather(weather_rows),
    )


def _build_laps(
    lap_rows: list[dict],
    stint_rows: list[dict],
    pit_rows: list[dict],
    driver_rows: list[dict],
) -> pd.DataFrame:
    columns = [
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
    acronym = {}
    for row in driver_rows:
        number = row.get("driver_number")
        if number is None:
            continue
        acronym[number] = str(row.get("name_acronym") or number)

    stints_by_driver: dict[int, list[dict]] = defaultdict(list)
    for row in stint_rows:
        number = row.get("driver_number")
        if number is None:
            continue
        stints_by_driver[number].append(row)
    for number, stints in list(stints_by_driver.items()):
        stints_by_driver[number] = normalize_stints(stints)

    pit_duration: dict[tuple[int, int], float] = {}
    for row in pit_rows:
        number = row.get("driver_number")
        lap_number = row.get("lap_number")
        if number is None or lap_number is None:
            continue
        # pit_duration is sometimes the lane transit (~25s) and sometimes only
        # the stationary stop (~2.5s). Prefer a lane time when we have one.
        duration = row.get("pit_duration")
        lane = row.get("lane_duration")
        if lane is not None and (duration is None or float(duration) < 15 <= float(lane)):
            duration = lane
        if duration is None:
            continue
        pit_duration[(number, int(lap_number))] = float(duration)

    records = []
    for row in lap_rows:
        number = row.get("driver_number")
        lap_number = row.get("lap_number")
        if number is None or lap_number is None:
            continue
        lap_number = int(lap_number)
        stint = _stint_for_lap(stints_by_driver.get(number, []), lap_number)
        compound = str((stint or {}).get("compound") or "UNKNOWN").upper()
        stint_number = int((stint or {}).get("stint_number") or 0)
        lap_start = int((stint or {}).get("lap_start") or lap_number)
        age = (stint or {}).get("tyre_age_at_start")
        if age is None:
            age = 0
        tyre_life = int(age) + (lap_number - lap_start) + 1
        if tyre_life < 1:
            tyre_life = 1

        is_pit_out = bool(row.get("is_pit_out_lap"))
        if stint is not None and stint_number > 1 and lap_number == lap_start:
            is_pit_out = True

        duration = pit_duration.get((number, lap_number))
        is_pit_in = duration is not None or _is_intermediate_stint_end(
            stints_by_driver.get(number, []), stint, lap_number
        )

        lap_duration = row.get("lap_duration")
        lap_time = pd.to_timedelta(float(lap_duration), unit="s") if lap_duration is not None else pd.NaT
        records.append(
            {
                "Driver": acronym.get(number, str(number)),
                "LapNumber": lap_number,
                "LapTime": lap_time,
                "Compound": compound,
                "TyreLife": tyre_life,
                "Stint": stint_number,
                "IsPitOut": is_pit_out,
                "IsPitIn": is_pit_in,
                "PitDuration": duration if duration is not None else pd.NA,
            }
        )

    if not records:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame.from_records(records, columns=columns)
    return frame.sort_values(["Driver", "LapNumber"]).reset_index(drop=True)


def normalize_stints(stints: list[dict]) -> list[dict]:
    """Give each lap to one stint.

    OpenF1 often sets the next stint's ``lap_start`` equal to the previous
    stint's ``lap_end``. That shared lap is the pit in-lap and keeps the old
    compound; the new stint starts on the following lap. A stint that sits
    entirely inside the next one (an aborted start) is dropped.
    """
    ordered = sorted(
        (row for row in stints if row.get("lap_start") is not None),
        key=lambda row: (row.get("stint_number") or 0, int(row["lap_start"])),
    )
    resolved: list[dict] = []
    for row in ordered:
        end = row.get("lap_end")
        current = {
            **row,
            "lap_start": int(row["lap_start"]),
            "lap_end": None if end is None else int(end),
        }
        if resolved:
            previous = resolved[-1]
            previous_end = previous.get("lap_end")
            if previous_end is not None and current["lap_start"] <= int(previous_end):
                if int(previous["lap_start"]) < current["lap_start"] and int(previous_end) - current["lap_start"] <= 1:
                    current["lap_start"] = int(previous_end) + 1
                elif int(previous["lap_start"]) >= current["lap_start"]:
                    resolved.pop()
        if current["lap_end"] is not None and current["lap_start"] > current["lap_end"]:
            continue
        resolved.append(current)
    return resolved


def _stint_for_lap(stints: list[dict], lap_number: int) -> dict | None:
    match = None
    for stint in stints:
        start = stint.get("lap_start")
        if start is None or lap_number < int(start):
            continue
        end = stint.get("lap_end")
        if end is not None and lap_number > int(end):
            continue
        match = stint
    return match


def _is_intermediate_stint_end(stints: list[dict], stint: dict | None, lap_number: int) -> bool:
    """True when this lap ends a stint that is followed by another one."""
    if stint is None:
        return False
    end = stint.get("lap_end")
    if end is None or int(end) != lap_number:
        return False
    stint_number = stint.get("stint_number") or 0
    return any((other.get("stint_number") or 0) > stint_number for other in stints)


def _build_weather(rows: list[dict]) -> pd.DataFrame:
    columns = ["AirTemp", "TrackTemp", "Humidity", "Rainfall", "WindSpeed"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        {
            "AirTemp": [row.get("air_temperature") for row in rows],
            "TrackTemp": [row.get("track_temperature") for row in rows],
            "Humidity": [row.get("humidity") for row in rows],
            "Rainfall": [1 if row.get("rainfall") else 0 for row in rows],
            "WindSpeed": [row.get("wind_speed") for row in rows],
        }
    )
