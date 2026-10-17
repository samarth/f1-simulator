# CLAUDE.md

Guidance for working with this F1 Strategy Simulator codebase.

## Overview

A web app for learning F1 race strategy through simulation. Users pick a historical race, plan their own pit stop strategy, and compare against what actually happened.

**Stack**: FastAPI backend + React/D3 frontend

## Architecture

### Backend (`backend/`)
- **Framework**: FastAPI + uvicorn, Python 3.13
- **Data Source**: [OpenF1](https://openf1.org) (`https://api.openf1.org/v1`). Historical endpoints are free and need no API key. Coverage starts in 2023.
- **Key Services**:
  - `openf1_client.py`: HTTP client, rate-limit pacing, in-memory response cache
  - `race_service.py`: Season list, race schedule, drivers, and lap/stint/pit/weather assembly
  - `strategy_service.py`: Tire degradation, pit stats, simulation engine

### Frontend (`frontend/`)
- **Framework**: React 19 + TypeScript + Vite 6
- **Styling**: Tailwind CSS v4 (`@import "tailwindcss"` + `@theme {}` in `src/index.css`)
- **Charts**: D3.js (React owns `<svg ref={}>`, D3 renders in `useEffect`)
- **State**: `useSession` context for race selection, `useReducer` for simulator state

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/years` | Seasons OpenF1 currently serves |
| GET | `/api/races?year=2024` | Race schedule for a season |
| GET | `/api/drivers?year=...&race=...&session=R` | Driver list (race session only) |
| GET | `/api/degradation?year=...&race=...` | Tire degradation curves |
| GET | `/api/pit-stats?year=...&race=...` | Pit stop duration stats |
| GET | `/api/actual-strategy?year=...&race=...&driver=VER` | What driver actually did |
| POST | `/api/simulate` | Run strategy simulation |
| GET | `/api/health` | Health check |

OpenF1 failures are returned as JSON `{"detail": "..."}` with 404 (no session or driver), 429 (rate limit), or 503 (unreachable). The UI shows that message.

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

### OpenF1 data
Laps, stints, pit stops, drivers, and weather are fetched per race session and joined into one table:

- `Driver` — `name_acronym` (VER, LEC, …)
- `LapTime` — `lap_duration` as a timedelta. Missing durations stay empty and are left out of the actual-lap total.
- `Compound` / `TyreLife` / `Stint` — from `/stints` (`tyre_age_at_start` plus laps into the stint)
- Pit-in laps come from `/pit`. Pit-out laps use `is_pit_out_lap` and the first lap of later stints. Those laps are excluded from the degradation fit.
- Two meetings in one season with the same name (two Bahrain grands prix) are labeled with the race date.

`OPENF1_BASE_URL` overrides the API origin (default `https://api.openf1.org/v1`).

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

- OpenF1 free tier is about 3 requests/second and 30 requests/minute. The client spaces calls and retries 429s.
- A first race load is a handful of requests (laps, stints, pit, drivers, weather), usually a few seconds.
- Repeat loads of the same race are served from an in-memory cache (about 6 hours for lap data, 30 minutes for the schedule).
- The year list is whatever `/sessions?session_name=Race` returns. It is not hardcoded.
