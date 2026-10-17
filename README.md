# F1 Strategy Simulator

A web app for learning Formula 1 race strategy. Pick a real race, plan your own pit stop strategy, and see how your choices would have played out compared to what actually happened.

## What You'll Learn

- **Tire degradation** — soft tires are fast but wear quickly, hard tires are slow but last
- **Pit stop math** — is a 2-stop strategy worth the extra ~25 seconds in the pits?
- **Strategy trade-offs** — when is staying out worth it vs pitting early?

## Features

- Real F1 data via the OpenF1 API (2023 onward)
- Interactive tire degradation charts (D3.js)
- Visual stint planner
- Lap-by-lap simulation comparison
- Cumulative gap visualization

## Quick Start

### Local Development

```bash
# Backend
cd backend
source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, proxies `/api` to backend.

### Docker

```bash
docker-compose up --build
```

App runs at `http://localhost` (nginx serves frontend, proxies API).

## How It Works

1. **Pick a race** — year and grand prix
2. **Pick your driver** — who are you engineering for?
3. **See the data** — tire degradation curves, pit stop time loss
4. **Plan your strategy** — add stints, choose compounds, set lap counts
5. **Simulate** — see lap-by-lap comparison vs actual race result

## Tech Stack

- **Backend**: FastAPI
- **Frontend**: React + Vite + D3.js + Tailwind CSS v4
- **Data**: [OpenF1](https://openf1.org) (`https://api.openf1.org/v1`)

## Project Structure

```
f1-simulator/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # Business logic
│   │   └── models/           # Pydantic schemas
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── layout/       # Header, SessionSelector
│   │   │   ├── strategy/     # Core simulator UI
│   │   │   └── common/       # Shared components
│   │   ├── api/              # API client
│   │   └── hooks/            # React hooks
│   └── package.json
└── docker-compose.yml
```

## Data Notes

- Timing comes from OpenF1. Historical endpoints are free and do not need an API key. Data starts with the 2023 season (there is no 2021 or 2022).
- The year menu lists every season OpenF1 currently publishes, including a season that is still in progress. A race that has not been run yet returns a clear error instead of an empty chart.
- The free tier allows about 3 requests per second and 30 per minute. The backend spaces its calls and keeps a short in-memory cache, so opening the same race again is immediate.
- Set `OPENF1_BASE_URL` if you need to point the backend at a different OpenF1 origin.
