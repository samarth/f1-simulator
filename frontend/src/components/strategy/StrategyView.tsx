import { useReducer, useEffect } from 'react';
import { useSession } from '../../hooks/useSession';
import { fetchDrivers, fetchDegradation, fetchPitStats, fetchActualStrategy, postSimulate } from '../../api';
import type { DriverInfo, DegradationResponse, PitStats, ActualStrategy, SimulateResponse, StintInput } from '../../types';
import LoadingOverlay from '../common/LoadingOverlay';
import CompoundBadge from '../common/CompoundBadge';
import DegradationChart from './DegradationChart';
import StintPlanner from './StintPlanner';
import LapTimeChart from './LapTimeChart';
import CumulativeGapChart from './CumulativeGapChart';
import ResultsSummary from './ResultsSummary';

interface RaceData {
  degradation: DegradationResponse;
  pitStats: PitStats;
  actual: ActualStrategy | null;
  totalLaps: number;
}

type State = {
  drivers: DriverInfo[];
  selectedDriver: string;
  raceData: RaceData | null;
  stints: StintInput[];
  simulation: SimulateResponse | null;
  loading: boolean;
  simulating: boolean;
  error: string;
};

type Action =
  | { type: 'SET_DRIVERS'; payload: DriverInfo[] }
  | { type: 'SET_DRIVER'; payload: string }
  | { type: 'SET_RACE_DATA'; payload: RaceData }
  | { type: 'SET_STINTS'; payload: StintInput[] }
  | { type: 'SET_SIMULATION'; payload: SimulateResponse }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_SIMULATING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'RESET_SIM' };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_DRIVERS': return { ...state, drivers: action.payload };
    case 'SET_DRIVER': return { ...state, selectedDriver: action.payload };
    case 'SET_RACE_DATA': return { ...state, raceData: action.payload, simulation: null };
    case 'SET_STINTS': return { ...state, stints: action.payload };
    case 'SET_SIMULATION': return { ...state, simulation: action.payload };
    case 'SET_LOADING': return { ...state, loading: action.payload };
    case 'SET_SIMULATING': return { ...state, simulating: action.payload };
    case 'SET_ERROR': return { ...state, error: action.payload };
    case 'RESET_SIM': return { ...state, simulation: null };
    default: return state;
  }
}

const initialStints: StintInput[] = [
  { compound: 'MEDIUM', laps: '' },
  { compound: 'HARD', laps: '' },
];

export default function StrategyView() {
  const { year, race } = useSession();
  const [state, dispatch] = useReducer(reducer, {
    drivers: [],
    selectedDriver: '',
    raceData: null,
    stints: initialStints,
    simulation: null,
    loading: false,
    simulating: false,
    error: '',
  });

  useEffect(() => {
    if (!race) return;
    fetchDrivers(year, race, 'R')
      .then((drivers) => dispatch({ type: 'SET_DRIVERS', payload: drivers }))
      .catch((e) => dispatch({ type: 'SET_ERROR', payload: e.message }));
  }, [year, race]);

  const handleLoadRaceData = async () => {
    if (!state.selectedDriver) {
      dispatch({ type: 'SET_ERROR', payload: 'Please select a driver.' });
      return;
    }
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: '' });

    try {
      const [degradation, pitStats, actual] = await Promise.all([
        fetchDegradation(year, race),
        fetchPitStats(year, race),
        fetchActualStrategy(year, race, state.selectedDriver).catch(() => null),
      ]);

      const totalLaps = actual?.total_laps ?? 57;

      dispatch({
        type: 'SET_RACE_DATA',
        payload: { degradation, pitStats, actual, totalLaps },
      });
    } catch (e: any) {
      dispatch({ type: 'SET_ERROR', payload: e.message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const handleSimulate = async () => {
    if (!state.raceData) return;

    const totalPlanned = state.stints.reduce((sum, s) => sum + (Number(s.laps) || 0), 0);
    if (totalPlanned !== state.raceData.totalLaps) {
      dispatch({ type: 'SET_ERROR', payload: `Total laps (${totalPlanned}) must equal race distance (${state.raceData.totalLaps}).` });
      return;
    }

    const uniqueCompounds = new Set(state.stints.map((s) => s.compound));
    if (uniqueCompounds.size < 2) {
      dispatch({ type: 'SET_ERROR', payload: 'Must use at least 2 different tire compounds.' });
      return;
    }

    dispatch({ type: 'SET_SIMULATING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: '' });

    try {
      const validStints = state.stints.map((s) => ({ compound: s.compound, laps: Number(s.laps) }));
      const result = await postSimulate(year, race, state.selectedDriver, validStints);
      dispatch({ type: 'SET_SIMULATION', payload: result });
    } catch (e: any) {
      dispatch({ type: 'SET_ERROR', payload: e.message });
    } finally {
      dispatch({ type: 'SET_SIMULATING', payload: false });
    }
  };

  const handleStintsChange = (stints: StintInput[]) => {
    dispatch({ type: 'SET_STINTS', payload: stints });
    dispatch({ type: 'RESET_SIM' });
  };

  const { raceData, stints, simulation } = state;
  const totalPlanned = stints.reduce((sum, s) => sum + (Number(s.laps) || 0), 0);

  return (
    <div>
      <div className="flex items-end gap-4 mb-6">
        <div className="flex flex-col gap-1">
          <label className="text-sm text-gray-400 font-body">Select Driver</label>
          <select
            value={state.selectedDriver}
            onChange={(e) => dispatch({ type: 'SET_DRIVER', payload: e.target.value })}
            className="bg-surface-500 text-white border border-surface-400 rounded px-3 py-2 font-body text-sm focus:outline-none focus:border-f1-red min-w-40"
          >
            <option value="">Choose driver...</option>
            {state.drivers.map((d) => (
              <option key={d.code} value={d.code}>
                {d.code} — {d.name}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleLoadRaceData}
          disabled={state.loading || !state.selectedDriver}
          className="bg-f1-red text-white px-6 py-2 rounded font-body font-semibold text-sm hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {state.loading ? 'Loading...' : 'Load Race Data'}
        </button>
      </div>

      {state.error && (
        <div className="bg-red-900/30 border border-red-700 text-red-300 px-4 py-2 rounded mb-4 text-sm">
          {state.error}
        </div>
      )}

      {state.loading && <LoadingOverlay message="Loading race data... This may take 30-60 seconds." />}

      {raceData && !state.loading && (
        <>
          <div className="bg-surface-600 rounded-lg p-4 mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span className="text-gray-400 text-xs block">Race Length</span>
              <span className="text-white font-mono text-lg">{raceData.totalLaps} laps</span>
            </div>
            <div>
              <span className="text-gray-400 text-xs block">Avg Pit Loss</span>
              <span className="text-white font-mono text-lg">~{raceData.pitStats.avg_pit_time.toFixed(1)}s</span>
            </div>
            <div>
              <span className="text-gray-400 text-xs block">Compounds Available</span>
              <div className="flex gap-1 mt-1">
                {Object.keys(raceData.degradation.compounds).map((c) => (
                  <CompoundBadge key={c} compound={c} />
                ))}
              </div>
            </div>
            <div>
              <span className="text-gray-400 text-xs block">{state.selectedDriver}'s Actual</span>
              <div className="flex items-center gap-1 mt-1 flex-wrap">
                {raceData.actual?.stints.map((s, i) => (
                  <span key={i} className="text-sm">
                    {i > 0 && <span className="text-gray-500 mx-0.5">&rarr;</span>}
                    <CompoundBadge compound={s.compound} />
                    <span className="text-gray-300 text-xs ml-0.5">({s.laps}L)</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <DegradationChart degradation={raceData.degradation} />

          <div className="bg-surface-700 rounded-lg p-5 mb-6">
            <h3 className="text-base font-display font-bold mb-4 text-gray-200">Plan Your Strategy</h3>

            <StintPlanner
              stints={stints}
              onChange={handleStintsChange}
              totalRaceLaps={raceData.totalLaps}
            />

            <div className="mt-3 mb-4 text-sm font-mono">
              {totalPlanned === 0 ? (
                <span className="text-gray-500">Enter lap counts (race is {raceData.totalLaps} laps)</span>
              ) : totalPlanned === raceData.totalLaps ? (
                <span className="text-green-400">Total: {totalPlanned} / {raceData.totalLaps} laps &#10003;</span>
              ) : totalPlanned < raceData.totalLaps ? (
                <span className="text-yellow-400">
                  Total: {totalPlanned} / {raceData.totalLaps} laps ({raceData.totalLaps - totalPlanned} remaining)
                </span>
              ) : (
                <span className="text-red-400">
                  Total: {totalPlanned} / {raceData.totalLaps} laps (exceeds by {totalPlanned - raceData.totalLaps}!)
                </span>
              )}
            </div>

            <button
              onClick={handleSimulate}
              disabled={state.simulating || totalPlanned !== raceData.totalLaps}
              className="bg-f1-red text-white px-8 py-2.5 rounded font-body font-semibold text-sm hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {state.simulating ? 'Simulating...' : 'Simulate Strategy'}
            </button>
          </div>

          {state.simulating && <LoadingOverlay message="Running simulation..." />}

          {simulation && (
            <div className="space-y-6">
              <ResultsSummary
                simulation={simulation}
                stints={stints}
                driver={state.selectedDriver}
              />
              <LapTimeChart
                simulation={simulation}
                stints={stints}
                driver={state.selectedDriver}
              />
              <CumulativeGapChart
                simulation={simulation}
                driver={state.selectedDriver}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
