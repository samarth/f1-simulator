def format_lap_time(timedelta_obj):
    """Convert timedelta to MM:SS.sss format."""
    total_seconds = timedelta_obj.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"


def format_race_time(total_seconds):
    """Convert total seconds to H:MM:SS.sss format."""
    hours = int(total_seconds // 3600)
    remaining = total_seconds % 3600
    minutes = int(remaining // 60)
    seconds = remaining % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:06.3f}"
    return f"{minutes}:{seconds:06.3f}"
