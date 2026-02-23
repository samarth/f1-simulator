import { useState } from 'react';
import CompoundBadge from '../common/CompoundBadge';

export default function F1Explainer() {
  const [open, setOpen] = useState(true);

  return (
    <div className="bg-surface-700 border border-surface-400 rounded-lg mb-6">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-display font-bold text-gray-300">
          New to F1 strategy?
        </span>
        <span className="text-gray-500 text-xs font-body">
          {open ? 'Hide' : 'Show'}
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 text-sm text-gray-300 font-body">
          {/* Tires */}
          <div>
            <h4 className="font-semibold text-gray-200 mb-1">Tire compounds</h4>
            <p className="mb-2">
              Each race has three dry tire compounds with different trade-offs:
            </p>
            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2">
                <CompoundBadge compound="SOFT" />
                <span className="text-gray-400">Fastest, but wears out quickly</span>
              </div>
              <div className="flex items-center gap-2">
                <CompoundBadge compound="MEDIUM" />
                <span className="text-gray-400">Balanced pace and durability</span>
              </div>
              <div className="flex items-center gap-2">
                <CompoundBadge compound="HARD" />
                <span className="text-gray-400">Slowest, but lasts the longest</span>
              </div>
            </div>
          </div>

          {/* Why pit */}
          <div>
            <h4 className="font-semibold text-gray-200 mb-1">Why pit?</h4>
            <p>
              Tires lose grip as they wear — each lap gets slower. At some point, swapping to
              fresh tires makes you faster overall, even though a pit stop costs ~20 seconds.
            </p>
          </div>

          {/* The trade-off */}
          <div>
            <h4 className="font-semibold text-gray-200 mb-1">The trade-off</h4>
            <p>
              More stops = more time in the pit lane, but fresher tires on track.
              Fewer stops = less time lost pitting, but slower pace on worn tires.
              Finding the right balance is what wins races.
            </p>
          </div>

          {/* How to use */}
          <div>
            <h4 className="font-semibold text-gray-200 mb-1">How to use this tool</h4>
            <ol className="list-decimal list-inside space-y-1 text-gray-400">
              <li>Pick a driver and load their race data</li>
              <li>Check the degradation chart to see how fast each compound wears</li>
              <li>Plan your stints — choose compounds and how many laps for each</li>
              <li>Hit simulate and see if your strategy beats what actually happened</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}
