"""OpenF1 stint bounds that share a lap."""

from app.services.race_service import normalize_stints


def test_shared_pit_lap_stays_with_the_old_compound():
    # Monaco 2024 shape: the hard stint starts on the medium stint's last lap,
    # and an aborted one-lap stint also claims lap 1.
    stints = [
        {"stint_number": 1, "compound": "HARD", "lap_start": 1, "lap_end": 1, "tyre_age_at_start": 0},
        {"stint_number": 2, "compound": "MEDIUM", "lap_start": 1, "lap_end": 52, "tyre_age_at_start": 0},
        {"stint_number": 3, "compound": "HARD", "lap_start": 52, "lap_end": 78, "tyre_age_at_start": 0},
    ]
    resolved = normalize_stints(stints)
    assert [(row["compound"], row["lap_start"], row["lap_end"]) for row in resolved] == [
        ("MEDIUM", 1, 52),
        ("HARD", 53, 78),
    ]


def test_non_overlapping_stints_are_unchanged():
    stints = [
        {"stint_number": 1, "compound": "SOFT", "lap_start": 1, "lap_end": 18},
        {"stint_number": 2, "compound": "HARD", "lap_start": 19, "lap_end": 57},
    ]
    resolved = normalize_stints(stints)
    assert [(row["lap_start"], row["lap_end"]) for row in resolved] == [(1, 18), (19, 57)]
