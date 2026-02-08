import { useSession } from '../../hooks/useSession';
import { SESSION_OPTIONS } from '../../constants/f1';

export default function SessionSelector() {
  const { year, setYear, race, setRace, session, setSession, races, loadingRaces } = useSession();

  return (
    <div className="bg-surface-800 px-6 py-4 flex flex-wrap gap-4 items-end border-b border-surface-400">
      <div className="flex flex-col gap-1">
        <label className="text-sm text-gray-400 font-body">Year</label>
        <select
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="bg-surface-500 text-white border border-surface-400 rounded px-3 py-2 font-body text-sm focus:outline-none focus:border-f1-red"
        >
          {[2024, 2023, 2022].map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1 min-w-48">
        <label className="text-sm text-gray-400 font-body">Race</label>
        <select
          value={race}
          onChange={(e) => setRace(e.target.value)}
          className="bg-surface-500 text-white border border-surface-400 rounded px-3 py-2 font-body text-sm focus:outline-none focus:border-f1-red"
          disabled={loadingRaces}
        >
          {loadingRaces && <option>Loading...</option>}
          {races.map((r) => (
            <option key={r.round} value={r.name}>{r.name}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-sm text-gray-400 font-body">Session</label>
        <select
          value={session}
          onChange={(e) => setSession(e.target.value)}
          className="bg-surface-500 text-white border border-surface-400 rounded px-3 py-2 font-body text-sm focus:outline-none focus:border-f1-red"
        >
          {SESSION_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
