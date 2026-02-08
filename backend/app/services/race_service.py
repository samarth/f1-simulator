import fastf1

from .session_service import load_session


def get_races(year: int) -> list[dict]:
    """Get race schedule for a given year."""
    schedule = fastf1.get_event_schedule(year)
    races = []
    for _, event in schedule.iterrows():
        # Skip testing events
        if event.get("EventFormat", "") == "testing":
            continue
        race_date = event.get("EventDate", "")
        date_str = str(race_date.date()) if hasattr(race_date, "date") else str(race_date)
        races.append({
            "round": int(event.get("RoundNumber", 0)),
            "name": str(event.get("EventName", "")),
            "country": str(event.get("Country", "")),
            "date": date_str,
        })
    # Filter out round 0 (pre-season testing)
    return [r for r in races if r["round"] > 0]


def get_drivers(year: int, race: str, session_type: str) -> list[dict]:
    """Get drivers for a given session, enriched with name/team from results."""
    session = load_session(year, race, session_type)
    driver_codes = sorted(session.laps["Driver"].unique().tolist())

    drivers = []
    results = session.results if hasattr(session, "results") and session.results is not None else None

    for code in driver_codes:
        name = code
        team = ""
        if results is not None and not results.empty:
            driver_row = results[results["Abbreviation"] == code]
            if not driver_row.empty:
                row = driver_row.iloc[0]
                full_name = row.get("FullName", "")
                if full_name:
                    name = str(full_name)
                team_name = row.get("TeamName", "")
                if team_name:
                    team = str(team_name)
        drivers.append({"code": code, "name": name, "team": team})

    return drivers
