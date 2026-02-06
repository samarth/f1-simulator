# F1 Pit Stop Strategy Simulator — Implementation Plan

## Context

The current `app.py` is a read-only telemetry analysis dashboard. The user wants to gamify it into a **pit stop strategy simulator** — a game where you play race engineer, decide when to pit and which tires to use, and see how your strategy compares against what actually happened using real F1 data.

FastF1 provides all the data needed: `Compound`, `TyreLife`, `Stint`, `PitInTime`, `PitOutTime`, `LapTime`, `Position` per lap, plus weather and track status.

## Game Concept

**You are the race engineer.** Pick a driver at a real race. The game shows you real tire degradation data from that race (lap times increasing as tires wear). You decide:
- Starting tire compound (Soft / Medium / Hard)
- When to pit (which lap numbers)
- What compound to switch to at each stop

The simulator uses **real degradation curves extracted from the actual race** to estimate what your strategy would have produced. At the end, compare your total race time against the driver's actual result.

## Architecture

### Tabbed Layout in `app.py`

Session selectors (Year / Race / Session) are shared above tabs:
- Tab 1: Telemetry Analysis (existing dashboard, unchanged)
- Tab 2: Strategy Simulator (new game mode)

### State Management — `dcc.Store` components

| Store ID | Type | Purpose |
|----------|------|---------|
| `strategy-state` | memory | Current game: driver, planned stops, degradation models |
| `strategy-history` | local | Persistent history of past strategy attempts |
| `num-stints-store` | memory | Track number of active stint input rows |

## Implementation Phases

### Phase 1: Core Structure + Data Layer
- Tab restructure with shared session selectors
- Session caching via `load_session()`
- Data extraction helpers: `get_race_degradation_data()`, `get_pit_stop_stats()`, `get_driver_actual_strategy()`

### Phase 2: Strategy Simulator UI
- Driver selector + Load Race Data button
- Race info card (race length, pit loss, compounds, rules)
- Tire degradation chart with real data + linear trendlines
- Dynamic stint planning with add/remove pit stop buttons
- Real-time lap count validation

### Phase 3: Simulation Engine
- `build_degradation_model()` — linear regression per compound
- `estimate_lap_time()` — base_time + deg_rate * tyre_life
- `simulate_strategy()` — lap-by-lap estimation with pit stop time loss

### Phase 4: Results & Comparison Visualization
- Lap Time Comparison chart (user vs actual with pit markers + compound bands)
- Cumulative Time Gap chart (shows where strategy gains/loses time)
- Summary card with total times, difference, and pit stop comparison

### Phase 5: Styling
- `assets/styles.css` with race info cards, result grids, F1-themed buttons, dark theme charts

## Files Modified

| File | Changes |
|------|---------|
| `app.py` | Tab restructure, strategy simulator layout + callbacks, simulation engine |
| `assets/styles.css` | New file — styling for strategy simulator components |
