import { useState, useRef, useCallback, useEffect } from 'react';
import { COMPOUND_COLORS } from '../../constants/f1';
import type { StintInput } from '../../types';

const COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD'] as const;
const COMPOUND_SHORT: Record<string, string> = { SOFT: 'S', MEDIUM: 'M', HARD: 'H' };
const MIN_STINT_LAPS = 3;
const MAX_PIT_STOPS = 4;

interface Props {
  stints: StintInput[];
  onChange: (stints: StintInput[]) => void;
  totalRaceLaps: number;
}

/** Convert StintInput[] to internal model: pit laps and compound per segment. */
function stintsToPits(stints: StintInput[]): { pitLaps: number[]; compounds: string[] } {
  const compounds = stints.map((s) => s.compound);
  const pitLaps: number[] = [];
  let cumulative = 0;
  for (let i = 0; i < stints.length - 1; i++) {
    cumulative += Number(stints[i].laps) || 0;
    pitLaps.push(cumulative);
  }
  return { pitLaps, compounds };
}

/** Convert internal model back to StintInput[]. */
function pitsToStints(pitLaps: number[], compounds: string[], totalLaps: number): StintInput[] {
  const boundaries = [0, ...pitLaps, totalLaps];
  return compounds.map((compound, i) => ({
    compound,
    laps: boundaries[i + 1] - boundaries[i],
  }));
}

export default function StintPlanner({ stints, onChange, totalRaceLaps }: Props) {
  const barRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<number | null>(null);

  const { pitLaps, compounds } = stintsToPits(stints);

  const updateFromInternal = useCallback(
    (pits: number[], comps: string[]) => {
      onChange(pitsToStints(pits, comps, totalRaceLaps));
    },
    [onChange, totalRaceLaps]
  );

  // Auto-fill even splits on first load when stints have empty laps
  useEffect(() => {
    const hasEmpty = stints.some((s) => s.laps === '' || s.laps === 0);
    if (hasEmpty && totalRaceLaps > 0) {
      const n = stints.length;
      const baseLaps = Math.floor(totalRaceLaps / n);
      const remainder = totalRaceLaps % n;
      const filled = stints.map((s, i) => ({
        compound: s.compound,
        laps: baseLaps + (i < remainder ? 1 : 0),
      }));
      onChange(filled);
    }
  }, [totalRaceLaps]); // Only on totalRaceLaps change (race load)

  // Drag handler
  const handlePointerDown = useCallback((dividerIndex: number) => {
    setDragging(dividerIndex);
  }, []);

  useEffect(() => {
    if (dragging === null) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!barRef.current) return;
      const rect = barRef.current.getBoundingClientRect();
      const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
      const fraction = x / rect.width;
      let newLap = Math.round(fraction * totalRaceLaps);

      // Enforce minimum stint lengths
      const prevBoundary = dragging === 0 ? 0 : pitLaps[dragging - 1];
      const nextBoundary = dragging === pitLaps.length - 1 ? totalRaceLaps : pitLaps[dragging + 1];
      newLap = Math.max(prevBoundary + MIN_STINT_LAPS, Math.min(newLap, nextBoundary - MIN_STINT_LAPS));

      if (newLap !== pitLaps[dragging]) {
        const newPits = [...pitLaps];
        newPits[dragging] = newLap;
        updateFromInternal(newPits, compounds);
      }
    };

    const handlePointerUp = () => setDragging(null);

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [dragging, pitLaps, compounds, totalRaceLaps, updateFromInternal]);

  const cycleCompound = (segmentIndex: number) => {
    const current = compounds[segmentIndex];
    const idx = COMPOUNDS.indexOf(current as typeof COMPOUNDS[number]);
    const next = COMPOUNDS[(idx + 1) % COMPOUNDS.length];
    const newCompounds = [...compounds];
    newCompounds[segmentIndex] = next;
    updateFromInternal(pitLaps, newCompounds);
  };

  const addPitStop = () => {
    if (pitLaps.length >= MAX_PIT_STOPS) return;
    // Find longest stint and split it
    const boundaries = [0, ...pitLaps, totalRaceLaps];
    let longestIdx = 0;
    let longestLen = 0;
    for (let i = 0; i < boundaries.length - 1; i++) {
      const len = boundaries[i + 1] - boundaries[i];
      if (len > longestLen) {
        longestLen = len;
        longestIdx = i;
      }
    }
    const mid = boundaries[longestIdx] + Math.floor(longestLen / 2);
    const newPits = [...pitLaps, mid].sort((a, b) => a - b);
    // Duplicate the compound for the split
    const newCompounds = [...compounds];
    newCompounds.splice(longestIdx + 1, 0, compounds[longestIdx]);
    updateFromInternal(newPits, newCompounds);
  };

  const removePitStop = (dividerIndex: number) => {
    if (pitLaps.length <= 1) return;
    const newPits = pitLaps.filter((_, i) => i !== dividerIndex);
    // Merge compounds: keep the one from the left segment
    const newCompounds = [...compounds];
    newCompounds.splice(dividerIndex + 1, 1);
    updateFromInternal(newPits, newCompounds);
  };

  // Compute segment widths
  const boundaries = [0, ...pitLaps, totalRaceLaps];
  const segments = compounds.map((compound, i) => ({
    compound,
    startLap: boundaries[i],
    endLap: boundaries[i + 1],
    laps: boundaries[i + 1] - boundaries[i],
    widthPct: ((boundaries[i + 1] - boundaries[i]) / totalRaceLaps) * 100,
  }));

  // Lap axis markers
  const markers: number[] = [];
  for (let lap = 10; lap < totalRaceLaps; lap += 10) {
    markers.push(lap);
  }

  return (
    <div className="select-none">
      {/* Timeline bar */}
      <div className="relative" ref={barRef}>
        <div className="flex h-14 rounded-lg overflow-hidden border border-surface-400">
          {segments.map((seg, i) => {
            const color = COMPOUND_COLORS[seg.compound] || '#666';
            const isLight = seg.compound === 'HARD' || seg.compound === 'MEDIUM';
            return (
              <div
                key={i}
                className="relative flex items-center justify-center cursor-pointer transition-opacity hover:opacity-90"
                style={{
                  width: `${seg.widthPct}%`,
                  backgroundColor: color,
                  minWidth: '24px',
                }}
                onClick={() => cycleCompound(i)}
                title={`Click to change compound (${seg.compound})`}
              >
                <div className={`text-center pointer-events-none ${isLight ? 'text-gray-900' : 'text-white'}`}>
                  <div className="text-xs font-bold font-mono leading-tight">
                    {COMPOUND_SHORT[seg.compound]}
                  </div>
                  <div className="text-[10px] font-mono opacity-80">
                    {seg.laps} laps
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Draggable dividers */}
        {pitLaps.map((lap, i) => {
          const pct = (lap / totalRaceLaps) * 100;
          return (
            <div
              key={i}
              className="absolute top-0 flex flex-col items-center"
              style={{
                left: `${pct}%`,
                transform: 'translateX(-50%)',
                height: '100%',
                zIndex: 10,
              }}
            >
              {/* Drag handle */}
              <div
                className={`w-5 h-full cursor-col-resize flex items-center justify-center group
                  ${dragging === i ? 'bg-white/30' : 'hover:bg-white/20'}`}
                onPointerDown={(e) => {
                  e.preventDefault();
                  handlePointerDown(i);
                }}
                style={{ touchAction: 'none' }}
              >
                <div className="w-0.5 h-8 bg-white/80 rounded-full" />
              </div>

              {/* Lap label */}
              <div className="absolute -bottom-6 bg-surface-600 border border-surface-400 rounded px-1.5 py-0.5 text-[10px] font-mono text-gray-300 whitespace-nowrap">
                L{lap}
                <button
                  className="ml-1 text-gray-500 hover:text-red-400 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    removePitStop(i);
                  }}
                  title="Remove pit stop"
                >
                  ×
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Lap axis */}
      <div className="relative h-6 mt-7 mx-0">
        <div className="absolute inset-x-0 top-0 h-px bg-surface-400" />
        {markers.map((lap) => (
          <div
            key={lap}
            className="absolute top-0 flex flex-col items-center"
            style={{ left: `${(lap / totalRaceLaps) * 100}%`, transform: 'translateX(-50%)' }}
          >
            <div className="w-px h-2 bg-surface-400" />
            <span className="text-[9px] text-gray-600 font-mono mt-0.5">{lap}</span>
          </div>
        ))}
        {/* Start and end labels */}
        <div className="absolute top-0 left-0 flex flex-col items-center">
          <div className="w-px h-2 bg-surface-400" />
          <span className="text-[9px] text-gray-600 font-mono mt-0.5">1</span>
        </div>
        <div className="absolute top-0 right-0 flex flex-col items-center">
          <div className="w-px h-2 bg-surface-400" />
          <span className="text-[9px] text-gray-600 font-mono mt-0.5">{totalRaceLaps}</span>
        </div>
      </div>

      {/* Add pit stop button */}
      <div className="mt-4">
        <button
          onClick={addPitStop}
          disabled={pitLaps.length >= MAX_PIT_STOPS}
          className="bg-surface-500 text-gray-300 border border-surface-400 px-3 py-1 rounded text-xs font-body hover:bg-surface-400 transition-colors disabled:opacity-40"
        >
          + Add Pit Stop
        </button>
        <span className="text-gray-500 text-xs ml-3">Click segments to change compound, drag dividers to adjust stint length</span>
      </div>
    </div>
  );
}
