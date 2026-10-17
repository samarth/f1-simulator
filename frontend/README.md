# Frontend

React + Vite UI for the F1 Strategy Simulator. The repository README explains the product and how the backend fits in.

```bash
npm install
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies `/api` to the backend on port 8000.

```bash
npx tsc --noEmit
npm run lint
npm run build
```

The year list is loaded from `GET /api/years`. If OpenF1 is down or a race has no laps, the message from the API is shown on the page.
