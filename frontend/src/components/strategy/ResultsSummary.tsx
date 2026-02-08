import type { SimulateResponse, StintInput, SuggestedStrategy } from '../../types';
import CompoundBadge from '../common/CompoundBadge';
import { COMPOUND_COLORS } from '../../constants/f1';

interface Props {
  simulation: SimulateResponse;
  stints: StintInput[];
  driver: string;
  onApplySuggestion?: (stints: StintInput[]) => void;
}

function formatRaceTime(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const remaining = totalSeconds % 3600;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${seconds.toFixed(3).padStart(6, '0')}`;
  }
  return `${minutes}:${seconds.toFixed(3).padStart(6, '0')}`;
}

export default function ResultsSummary({ simulation, stints, driver, onApplySuggestion }: Props) {
  const { user_total_time, actual, stint_analysis, suggested_strategies } = simulation;
  const actualTotal = actual?.total_time ?? 0;
  const diff = actualTotal > 0 ? user_total_time - actualTotal : 0;
  const absDiff = Math.abs(diff);
  const isFaster = diff < 0;

  const userStops: { lap: number; from: string; to: string }[] = [];
  let stintStart = 0;
  for (let i = 0; i < stints.length - 1; i++) {
    const laps = Number(stints[i].laps) || 0;
    const pitLap = stintStart + laps;
    userStops.push({
      lap: pitLap,
      from: stints[i].compound,
      to: stints[i + 1].compound,
    });
    stintStart += laps;
  }

  const actualStops = actual?.pit_laps ?? [];

  const handleTryStrategy = (suggestion: SuggestedStrategy) => {
    if (!onApplySuggestion) return;
    const newStints: StintInput[] = suggestion.stints.map((s) => ({
      compound: s.compound,
      laps: s.laps,
    }));
    onApplySuggestion(newStints);
  };

  return (
    <div className="bg-surface-600 rounded-lg p-5">
      <h3 className="text-base font-display font-bold mb-4 text-gray-200">Results Summary</h3>

      {/* Main verdict */}
      <div className={`rounded-lg p-4 mb-5 text-center ${isFaster ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'}`}>
        <span className={`text-2xl font-bold ${isFaster ? 'text-green-400' : 'text-red-400'}`}>
          {actualTotal > 0 ? (
            isFaster ? `${absDiff.toFixed(3)}s FASTER!` : `${absDiff.toFixed(3)}s slower`
          ) : 'No comparison available'}
        </span>
        <p className="text-gray-400 text-sm mt-1">
          {isFaster ? 'Your strategy would have beaten the actual result!' : 'The actual strategy was better this time.'}
        </p>
      </div>

      {/* Time breakdown */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div className="bg-surface-700 rounded-lg p-4">
          <span className="text-gray-400 text-xs block mb-1">Your Total Time</span>
          <span className="text-accent-cyan font-mono text-xl font-bold">
            {formatRaceTime(user_total_time)}
          </span>
          <div className="mt-2 text-xs text-gray-500">
            {stints.length - 1} pit stop{stints.length - 1 !== 1 ? 's' : ''}
          </div>
        </div>
        <div className="bg-surface-700 rounded-lg p-4">
          <span className="text-gray-400 text-xs block mb-1">{driver}'s Actual Time</span>
          <span className="text-accent-coral font-mono text-xl font-bold">
            {actualTotal > 0 ? formatRaceTime(actualTotal) : 'N/A'}
          </span>
          <div className="mt-2 text-xs text-gray-500">
            {actualStops.length} pit stop{actualStops.length !== 1 ? 's' : ''}
          </div>
        </div>
      </div>

      {/* Pit stop comparison */}
      <div className="grid grid-cols-2 gap-4 text-sm mb-6">
        <div>
          <span className="text-accent-cyan text-xs font-semibold block mb-2">YOUR PIT STOPS</span>
          {userStops.length > 0 ? (
            <div className="space-y-1">
              {userStops.map((stop, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-gray-400 font-mono">Lap {stop.lap}:</span>
                  <CompoundBadge compound={stop.from} />
                  <span className="text-gray-500">&rarr;</span>
                  <CompoundBadge compound={stop.to} />
                </div>
              ))}
            </div>
          ) : (
            <span className="text-gray-500">No stops</span>
          )}
        </div>
        <div>
          <span className="text-accent-coral text-xs font-semibold block mb-2">{driver}'s ACTUAL STOPS</span>
          {actualStops.length > 0 ? (
            <div className="space-y-1">
              {actualStops.map((stop, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-gray-400 font-mono">Lap {stop.lap}:</span>
                  <CompoundBadge compound={stop.from_compound} />
                  <span className="text-gray-500">&rarr;</span>
                  <CompoundBadge compound={stop.to_compound} />
                </div>
              ))}
            </div>
          ) : (
            <span className="text-gray-500">No stops</span>
          )}
        </div>
      </div>

      {/* Per-Stint Breakdown */}
      {stint_analysis && stint_analysis.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-display font-semibold text-gray-300 mb-3">Per-Stint Breakdown</h4>
          <div className="space-y-2">
            {stint_analysis.map((sa) => {
              const isGain = sa.delta < 0;
              const absDelta = Math.abs(sa.delta);
              const barWidth = Math.min(absDelta / 10, 1) * 100; // scale: 10s = full width
              return (
                <div key={sa.stint} className="bg-surface-700 rounded-lg p-3">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-gray-400 text-xs font-mono w-14">Stint {sa.stint}</span>
                    <CompoundBadge compound={sa.compound} />
                    <span className="text-gray-500 text-xs">{sa.laps} laps</span>
                    <span className={`ml-auto font-mono text-sm font-bold ${isGain ? 'text-green-400' : 'text-red-400'}`}>
                      {isGain ? '-' : '+'}{absDelta.toFixed(1)}s
                    </span>
                  </div>
                  {/* Delta bar */}
                  <div className="h-1.5 bg-surface-500 rounded-full mb-2">
                    <div
                      className={`h-full rounded-full ${isGain ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                  <p className="text-gray-400 text-xs">{sa.explanation}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Suggested Strategies */}
      {suggested_strategies && suggested_strategies.length > 0 && (
        <div>
          <h4 className="text-sm font-display font-semibold text-gray-300 mb-3">Suggested Strategies</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {suggested_strategies.map((suggestion, i) => {
              const isGain = suggestion.delta_vs_actual < 0;
              const absDelta = Math.abs(suggestion.delta_vs_actual);
              return (
                <div key={i} className="bg-surface-700 rounded-lg p-4 border border-surface-400">
                  <div className="text-xs font-semibold text-gray-400 mb-2">{suggestion.label}</div>
                  {/* Compound sequence as mini bar */}
                  <div className="flex h-5 rounded overflow-hidden mb-2">
                    {suggestion.stints.map((s, j) => (
                      <div
                        key={j}
                        className="flex items-center justify-center text-[9px] font-mono font-bold"
                        style={{
                          backgroundColor: COMPOUND_COLORS[s.compound] || '#666',
                          flexGrow: s.laps,
                          color: s.compound === 'HARD' || s.compound === 'MEDIUM' ? '#111' : '#fff',
                        }}
                      >
                        {s.laps}
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-gray-400 text-xs font-mono">{formatRaceTime(suggestion.total_time)}</span>
                    <span className={`text-xs font-mono font-bold ${isGain ? 'text-green-400' : 'text-red-400'}`}>
                      {isGain ? '-' : '+'}{absDelta.toFixed(1)}s vs actual
                    </span>
                  </div>
                  {onApplySuggestion && (
                    <button
                      onClick={() => handleTryStrategy(suggestion)}
                      className="w-full bg-surface-500 text-gray-200 border border-surface-400 px-3 py-1.5 rounded text-xs font-body hover:bg-surface-400 hover:text-white transition-colors"
                    >
                      Try this strategy
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
