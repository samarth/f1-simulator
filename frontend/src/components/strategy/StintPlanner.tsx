import { COMPOUND_OPTIONS, MAX_STINTS, COMPOUND_COLORS } from '../../constants/f1';
import type { StintInput } from '../../types';

interface Props {
  stints: StintInput[];
  onChange: (stints: StintInput[]) => void;
  totalRaceLaps: number;
}

export default function StintPlanner({ stints, onChange }: Props) {
  const updateStint = (index: number, field: keyof StintInput, value: string | number) => {
    const next = [...stints];
    if (field === 'laps') {
      next[index] = { ...next[index], laps: value === '' ? '' : Number(value) };
    } else {
      next[index] = { ...next[index], [field]: value as string };
    }
    onChange(next);
  };

  const addStint = () => {
    if (stints.length >= MAX_STINTS) return;
    onChange([...stints, { compound: 'HARD', laps: '' }]);
  };

  const removeStint = () => {
    if (stints.length <= 2) return;
    onChange(stints.slice(0, -1));
  };

  return (
    <div>
      <div className="space-y-3">
        {stints.map((stint, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-gray-400 text-sm font-mono w-16">Stint {i + 1}</span>
            <select
              value={stint.compound}
              onChange={(e) => updateStint(i, 'compound', e.target.value)}
              className="bg-surface-500 text-white border border-surface-400 rounded px-3 py-1.5 text-sm font-body focus:outline-none focus:border-f1-red appearance-none pr-8"
              style={{ borderLeftColor: COMPOUND_COLORS[stint.compound] || '#444', borderLeftWidth: '3px' }}
            >
              {COMPOUND_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <span className="text-gray-500 text-sm">for</span>
            <input
              type="number"
              min={1}
              max={80}
              value={stint.laps}
              onChange={(e) => updateStint(i, 'laps', e.target.value)}
              placeholder="laps"
              className="bg-surface-500 text-white border border-surface-400 rounded px-3 py-1.5 text-sm font-mono w-20 text-center focus:outline-none focus:border-f1-red"
            />
            <span className="text-gray-500 text-sm">laps</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={addStint}
          disabled={stints.length >= MAX_STINTS}
          className="bg-surface-500 text-gray-300 border border-surface-400 px-3 py-1 rounded text-xs font-body hover:bg-surface-400 transition-colors disabled:opacity-40"
        >
          + Add Pit Stop
        </button>
        <button
          onClick={removeStint}
          disabled={stints.length <= 2}
          className="bg-surface-500 text-gray-300 border border-surface-400 px-3 py-1 rounded text-xs font-body hover:bg-surface-400 transition-colors disabled:opacity-40"
        >
          &minus; Remove Pit Stop
        </button>
      </div>
    </div>
  );
}
