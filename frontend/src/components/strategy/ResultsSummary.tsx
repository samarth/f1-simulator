import type { SimulateResponse, StintInput } from '../../types';

interface Props {
  simulation: SimulateResponse;
  stints: StintInput[];
  driver: string;
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

export default function ResultsSummary({ simulation, stints, driver }: Props) {
  const { user_total_time, actual } = simulation;
  const actualTotal = actual?.total_time ?? 0;
  const diff = actualTotal > 0 ? user_total_time - actualTotal : 0;
  const diffSign = diff > 0 ? '+' : '';
  const diffLabel = diff > 0 ? 'slower' : 'faster';
  const diffColor = diff > 0 ? 'text-accent-coral' : 'text-green-400';

  const userStops: string[] = [];
  let stintStart = 0;
  for (let i = 0; i < stints.length - 1; i++) {
    const laps = Number(stints[i].laps) || 0;
    const pitLap = stintStart + laps;
    const from = stints[i].compound[0];
    const to = stints[i + 1].compound[0];
    userStops.push(`L${pitLap} (${from}\u2192${to})`);
    stintStart += laps;
  }

  const actualStops = actual?.pit_laps?.map(
    (p) => `L${p.lap} (${p.from_compound[0]}\u2192${p.to_compound[0]})`
  ) ?? [];

  return (
    <div className="bg-surface-600 rounded-lg p-5">
      <h3 className="text-base font-display font-bold mb-4 text-gray-200">Results Summary</h3>

      <div className="grid grid-cols-3 gap-4 mb-5">
        <div className="bg-surface-700 rounded-lg p-4 text-center">
          <span className="text-gray-400 text-xs block mb-1">Your Total Time</span>
          <span className="text-accent-cyan font-mono text-xl font-bold">
            {formatRaceTime(user_total_time)}
          </span>
        </div>
        <div className="bg-surface-700 rounded-lg p-4 text-center">
          <span className="text-gray-400 text-xs block mb-1">{driver}'s Actual Time</span>
          <span className="text-accent-coral font-mono text-xl font-bold">
            {actualTotal > 0 ? formatRaceTime(actualTotal) : 'N/A'}
          </span>
        </div>
        <div className="bg-surface-700 rounded-lg p-4 text-center">
          <span className="text-gray-400 text-xs block mb-1">Difference</span>
          <span className={`font-mono text-xl font-bold ${diffColor}`}>
            {actualTotal > 0 ? `${diffSign}${Math.abs(diff).toFixed(3)}s (${diffLabel})` : 'N/A'}
          </span>
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div>
          <span className="text-gray-400">Your Pit Stops: </span>
          <span className="text-white font-mono">{userStops.length > 0 ? userStops.join(', ') : 'None'}</span>
        </div>
        <div>
          <span className="text-gray-400">{driver}'s Actual Stops: </span>
          <span className="text-white font-mono">{actualStops.length > 0 ? actualStops.join(', ') : 'None'}</span>
        </div>
      </div>
    </div>
  );
}
