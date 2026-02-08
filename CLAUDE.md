# CLAUDE.md

Guidance for working with this F1 Strategy Simulator codebase.

## Overview

A web app for learning F1 race strategy through simulation. Users pick a historical race, plan their own pit stop strategy, and compare against what actually happened.

**Stack**: FastAPI backend + React/D3 frontend

## Architecture

### Backend (`backend/`)
- **Framework**: FastAPI + uvicorn, Python 3.13
- **Data Source**: FastF1 library for official F1 timing data
- **Key Services**:
  - `session_service.py`: Thread-safe FastF1 loading with semaphore + per-key locks
  - `race_service.py`: Race schedule and driver listing
  - `strategy_service.py`: Tire degradation, pit stats, simulation engine

### Frontend (`frontend/`)
- **Framework**: React 18 + TypeScript + Vite 6
- **Styling**: Tailwind CSS v4 (`@import "tailwindcss"` + `@theme {}` in `src/index.css`)
- **Charts**: D3.js (React owns `<svg ref={}>`, D3 renders in `useEffect`)
- **State**: `useSession` context for race selection, `useReducer` for simulator state

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/races?year=2024` | Race schedule |
| GET | `/api/drivers?year=...&race=...&session=R` | Driver list |
| GET | `/api/degradation?year=...&race=...` | Tire degradation curves |
| GET | `/api/pit-stats?year=...&race=...` | Pit stop duration stats |
| GET | `/api/actual-strategy?year=...&race=...&driver=VER` | What driver actually did |
| POST | `/api/simulate` | Run strategy simulation |
| GET | `/api/health` | Health check |

## Commands

```bash
# Backend
cd backend && source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev    # Dev server on :5173
cd frontend && npx tsc --noEmit  # Type check

# Docker
docker-compose up --build
```

## Key Implementation Details

### FastF1 Data
- `session.laps` DataFrame: `Driver`, `LapTime`, `Compound`, `TyreLife`, `Stint`
- Use `lap['LapTime']` (duration), NOT `lap['Time']` (timestamp)
- Filters: `pick_tyre()`, `pick_wo_box()`, `pick_accurate()`

### Degradation Model
Linear regression: `lap_time = base_time + deg_rate × tyre_life`

### Compound Colors
- SOFT: `#FF3333`
- MEDIUM: `#FFC300`
- HARD: `#FFFFFF`

### Chart Colors
- User strategy: `#00BFFF` (cyan)
- Actual: `#FF6B6B` (coral)
- Gap: `#FFD700` (gold)

## Performance

- First race load: 30-60s (FastF1 download)
- Cached loads: ~2s
- Memory: ~500MB per session
- Max 2 concurrent FastF1 loads (semaphore)
