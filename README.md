# F1 Strategy Simulator

A web app for learning Formula 1 race strategy. Pick a real race, plan your own pit stop strategy, and see how your choices would have played out compared to what actually happened.

## What You'll Learn

- **Tire degradation** — soft tires are fast but wear quickly, hard tires are slow but last
- **Pit stop math** — is a 2-stop strategy worth the extra ~25 seconds in the pits?
- **Strategy trade-offs** — when is staying out worth it vs pitting early?

## Features

- Real F1 data via FastF1
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

- **Backend**: FastAPI + FastF1
- **Frontend**: React + Vite + D3.js + Tailwind CSS v4
- **Data**: Official F1 timing data via FastF1 library

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

- First load of a race takes 30-60 seconds (downloading from F1)
- Subsequent loads are cached (~2 seconds)
- Cache stored in `backend/cache/`
