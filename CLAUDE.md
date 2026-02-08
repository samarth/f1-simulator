# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

Split frontend/backend F1 telemetry analysis and strategy simulation system.

### Backend: FastAPI (`backend/`)
- **Framework**: FastAPI + uvicorn, Python 3.13
- **Data Source**: FastF1 library for official F1 telemetry and timing data
- **Structure**: `app/` with routers, services, models (Pydantic), and utils
- **Key Services**:
  - `session_service.py`: Thread-safe FastF1 loading — `Semaphore(2)` + per-key `threading.Lock`. Auto-creates cache dir on import.
  - `race_service.py`: Race schedule (`fastf1.get_event_schedule()`) and driver listing (enriched from `session.results`)
  - `telemetry_service.py`: Track map + speed comparison with pre-interpolation (200 speed points, ~500 track points per driver)
  - `strategy_service.py`: Tire degradation curves, pit stats, actual strategy extraction, lap time simulation engine

### Frontend: React + Vite + Tailwind + D3.js (`frontend/`)
- **Framework**: React 18 + TypeScript, Vite 6, Node 22
- **Styling**: Tailwind CSS v4 with `@import "tailwindcss"` + `@theme {}` in `src/index.css` (NOT the old `@tailwind` directives)
- **Tailwind Plugin**: Uses `@tailwindcss/vite` in `vite.config.ts` (NOT PostCSS config)
- **Visualizations**: D3.js — React owns `<svg ref={svgRef}>`, D3 renders inside `useEffect`, clears with `svg.selectAll('*').remove()` on redraw
- **State**: `useSession` (React Context) for shared year/race/session; `useReducer` for strategy simulator state
- **Fonts**: Google Fonts loaded in `index.html` — Titillium Web (display), Inter (body), JetBrains Mono (mono)

### Legacy Files (repo root, kept for reference)
- `app.py`: Original monolithic Dash app (~1150 lines)
- `main.py`: Original matplotlib analysis script
- `assets/styles.css`: Old Dash CSS overrides

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/races?year=2024` | Race schedule from FastF1 |
| GET | `/api/drivers?year=2024&race=...&session=R` | Drivers with name/team info |
| GET | `/api/telemetry?year=...&race=...&session=...&drivers=VER,HAM` | Pre-interpolated telemetry |
| GET | `/api/degradation?year=...&race=...` | Tire degradation curves + linear model coefficients |
| GET | `/api/pit-stats?year=...&race=...` | Pit stop duration statistics |
| GET | `/api/actual-strategy?year=...&race=...&driver=VER` | Driver's actual race strategy |
| POST | `/api/simulate` | Run strategy simulation (body: `{year, race, driver, stints}`) |
| GET | `/api/health` | Health check |

## Common Commands

### Local Development
```bash
# Backend (uses existing .venv at project root)
source .venv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev  # Vite dev server on :5173, proxies /api → localhost:8000

# Type-check frontend
cd frontend && npx tsc --noEmit

# Build frontend for production
cd frontend && npm run build
```

### Docker
```bash
docker-compose up --build       # Full stack: backend :8000 + frontend/nginx :80
docker-compose up backend       # Backend only
```

### Data Management
- **Cache Location**: `backend/cache/` (auto-created on first run), or set `FASTF1_CACHE_DIR` env var
- **Cache Size**: ~100MB per F1 session
- **Docker**: Mount `./cache:/app/cache` volume for persistence

## Key Implementation Details

### FastF1 Data
- **Sessions**: `fastf1.get_session(year, race, session_type)` then `session.load()`
- **Lap Data**: `session.laps` DataFrame — columns include `Driver`, `LapTime`, `Time`, `LapNumber`, `Compound`, `TyreLife`, `Stint`
- **Telemetry**: `lap.get_telemetry()` → DataFrame with `X`, `Y`, `Speed`, `Distance`
- **Key Filters**: `laps.pick_tyre(compound)`, `laps.pick_wo_box()` (exclude pit laps), `laps.pick_accurate()`
- **Lap Time Bug**: Always use `lap['LapTime']` (duration), NOT `lap['Time']` (session timestamp)

### Backend Patterns
- All route handlers are **sync** (FastAPI auto-threads them) — appropriate since FastF1 `session.load()` is blocking I/O
- `session_service.py` caches loaded sessions in `_session_cache` dict with double-checked locking
- Time formatting utilities in `backend/app/utils/formatting.py`: `format_lap_time()` → `MM:SS.sss`, `format_race_time()` → `H:MM:SS.sss`
- Degradation model: linear regression via `numpy.polyfit(tyre_life, avg_times, 1)` → `base_time + deg_rate * tyre_life`

### Frontend Patterns
- **D3 Tooltips**: Separate `<div ref={tooltipRef}>` positioned absolutely over SVG container, styled with Tailwind
- **API Layer**: `src/api/index.ts` — typed fetch wrappers with error extraction from FastAPI `detail` field
- **Driver Selection**: Toggle buttons (telemetry tab), dropdown (strategy tab)
- **Compound Colors**: `SOFT=#FF3333`, `MEDIUM=#FFC300`, `HARD=#FFFFFF` — defined in `src/constants/f1.ts`
- **Chart Colors**: User strategy = `#00BFFF` (cyan), Actual = `#FF6B6B` (coral), Gap = `#FFD700` (gold)

### Tailwind v4 Theme
Custom colors defined in `frontend/src/index.css` via `@theme {}`:
- Surface scale: `surface-900` (#0F0F0F) through `surface-400` (#444444)
- Accent: `f1-red` (#E10600), `accent-cyan`, `accent-coral`, `accent-gold`
- Font families: `font-display`, `font-body`, `font-mono`

### Performance
- **First session load**: 30-60 seconds (FastF1 downloads from F1 API)
- **Cached loads**: ~2 seconds
- **Memory**: ~500MB RAM per loaded session
- **Concurrency**: Max 2 simultaneous FastF1 loads (semaphore in `session_service.py`)

## Project Structure

```
f1-simulator/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router includes
│   │   ├── config.py            # CACHE_DIR, CORS_ORIGINS, MAX_CONCURRENT_LOADS
│   │   ├── models/              # Pydantic: common.py, telemetry.py, strategy.py
│   │   ├── services/            # Business logic: session, race, telemetry, strategy
│   │   ├── routers/             # API routes: races, drivers, telemetry, strategy, simulate
│   │   └── utils/formatting.py  # format_lap_time(), format_race_time()
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Root: SessionProvider + Header + Tabs
│   │   ├── api/index.ts         # Typed fetch wrappers
│   │   ├── types/index.ts       # TypeScript interfaces
│   │   ├── constants/f1.ts      # Colors, options, limits
│   │   ├── hooks/useSession.tsx # Shared session context
│   │   └── components/
│   │       ├── layout/          # Header, SessionSelector, TabNav
│   │       ├── common/          # LoadingOverlay, CompoundBadge
│   │       ├── telemetry/       # TelemetryView, TrackMap (D3), SpeedComparison (D3)
│   │       └── strategy/        # StrategyView, DegradationChart (D3), StintPlanner,
│   │                            # LapTimeChart (D3), CumulativeGapChart (D3), ResultsSummary
│   ├── index.html, vite.config.ts, package.json
│   ├── nginx.conf               # Production: proxies /api/ → backend:8000
│   └── Dockerfile
├── docker-compose.yml           # backend (:8000) + frontend/nginx (:80)
├── .venv/                       # Python 3.13 virtualenv (shared)
├── app.py                       # Legacy Dash app (reference only)
└── main.py                      # Legacy matplotlib script (reference only)
```
