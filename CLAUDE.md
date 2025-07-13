# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This repository contains a dual-architecture F1 telemetry analysis system:

### Primary Application: Interactive Web Dashboard (`app.py`)
- **Framework**: Dash (Flask-based) with Plotly visualizations
- **Data Source**: FastF1 library for official F1 telemetry and timing data
- **Architecture**: Single-page application with reactive callbacks
- **Core Components**:
  - Interactive dropdowns for year/race/session/driver selection
  - Track visualization with speed color-coding using X/Y coordinates
  - Speed comparison charts with interpolated data along track distance
  - Real-time data loading and caching system

### Legacy Analysis Script (`main.py`)
- **Framework**: Matplotlib for static visualizations  
- **Purpose**: Original proof-of-concept and debugging tool
- **Output**: Static PNG files for track maps and speed comparisons

### Data Flow
1. **FastF1 Integration**: `fastf1.get_session()` loads F1 data from official APIs
2. **Telemetry Processing**: Extract `LapTime` (lap duration) vs `Time` (session timestamp) 
3. **Speed Interpolation**: Use `np.interp()` to align drivers on common distance points
4. **Interactive Callbacks**: Dash `@callback` decorators trigger on user input changes

## Common Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py  # Dash app on http://localhost:8050

# Run legacy matplotlib analysis
MPLBACKEND=Agg python main.py  # Generates PNG files
```

### Docker Development
```bash
# Build container
docker build -t f1-telemetry-app .

# Run with persistent cache
docker run -p 8050:8050 -v $(pwd)/cache:/app/cache f1-telemetry-app

# Development with Docker Compose
docker-compose up --build

# Production with nginx proxy
docker-compose --profile production up --build
```

### Data Management
- **Cache Location**: `./cache/` (FastF1 stores ~100MB per session)
- **Environment Variable**: `FASTF1_CACHE_DIR=/app/cache`
- **Cache Persistence**: Always mount cache volume in containers for performance

## Key Implementation Details

### FastF1 Data Structure
- **Sessions**: `fastf1.get_session(year, race, session_type)`
- **Lap Data**: `session.laps` DataFrame with columns `['Driver', 'LapTime', 'Time', 'LapNumber']`
- **Telemetry**: `lap.get_telemetry()` returns DataFrame with `['X', 'Y', 'Speed', 'Distance', 'Throttle', 'Brake']`

### Critical Data Handling
- **Lap Time Bug**: Always use `lap['LapTime']` (duration) not `lap['Time']` (session timestamp)
- **Time Formatting**: Use custom `format_lap_time()` function to convert timedelta to "MM:SS.sss" format
- **Driver Selection**: Filter laps with `laps[laps['Driver'] == driver_code]`
- **Fastest Lap**: Use `laps.pick_fastest()` for overall or `driver_laps.pick_fastest()` per driver
- **Server Exposure**: Dash apps need `server = app.server` for Gunicorn deployment

### Plotly Visualization Patterns
- **Track Maps**: `go.Scatter()` with `x=telemetry['X'], y=telemetry['Y'], color=telemetry['Speed']`
- **Speed Traces**: `go.Scatter()` with `mode='lines'` and interpolated data
- **Interactive Features**: Hover templates with `hovertemplate` and `customdata`
- **Layout Best Practices**: Single colorbar per chart, horizontal legends below plots, adequate margins to prevent text overlap

### Container Configuration
- **Base Image**: `python:3.9-slim` with gcc/g++ for FastF1 compilation
- **Production Server**: Gunicorn with 300s timeout for F1 data loading
- **Security**: Non-root user, health checks, resource limits
- **Port**: 8050 (Dash default)

### Performance Considerations
- **Initial Load Time**: 30-60 seconds per F1 session (first time)
- **Memory Usage**: ~500MB RAM per loaded session
- **Cache Strategy**: FastF1 caches all downloaded data locally
- **Concurrent Users**: Single Gunicorn worker handles ~10 users efficiently