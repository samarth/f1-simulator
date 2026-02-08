import { useState, useEffect } from 'react';
import { useSession } from '../../hooks/useSession';
import { fetchDrivers, fetchTelemetry } from '../../api';
import type { DriverInfo, TelemetryResponse } from '../../types';
import LoadingOverlay from '../common/LoadingOverlay';
import TrackMap from './TrackMap';
import SpeedComparison from './SpeedComparison';

export default function TelemetryView() {
  const { year, race, session } = useSession();
  const [drivers, setDrivers] = useState<DriverInfo[]>([]);
  const [selectedDrivers, setSelectedDrivers] = useState<string[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDrivers, setLoadingDrivers] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!race) return;
    let cancelled = false;
    setLoadingDrivers(true);
    fetchDrivers(year, race, session)
      .then((data) => {
        if (cancelled) return;
        setDrivers(data);
        const defaults = data.slice(0, 3).map((d) => d.code);
        setSelectedDrivers(defaults);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoadingDrivers(false); });
    return () => { cancelled = true; };
  }, [year, race, session]);

  useEffect(() => {
    if (!race || selectedDrivers.length === 0) {
      setTelemetry(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetchTelemetry(year, race, session, selectedDrivers)
      .then((data) => { if (!cancelled) setTelemetry(data); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [year, race, session, selectedDrivers]);

  const toggleDriver = (code: string) => {
    setSelectedDrivers((prev) =>
      prev.includes(code) ? prev.filter((d) => d !== code) : [...prev, code]
    );
  };

  return (
    <div>
      <div className="mb-6">
        <label className="text-sm text-gray-400 font-body block mb-2">Select Drivers to Compare</label>
        <div className="flex flex-wrap gap-2">
          {loadingDrivers && <span className="text-gray-500 text-sm">Loading drivers...</span>}
          {drivers.map((d) => (
            <button
              key={d.code}
              onClick={() => toggleDriver(d.code)}
              className={`px-3 py-1.5 rounded text-sm font-mono font-bold transition-colors ${
                selectedDrivers.includes(d.code)
                  ? 'bg-f1-red text-white'
                  : 'bg-surface-600 text-gray-300 hover:bg-surface-500'
              }`}
            >
              {d.code}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-red-400 mb-4">{error}</p>}

      {loading && <LoadingOverlay message="Loading telemetry data... This may take 30-60 seconds for uncached sessions." />}

      {!loading && telemetry && (
        <>
          <div className="bg-surface-600 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-display font-bold mb-1">
              {year} {race} GP &mdash; {session} Session
            </h3>
            <p className="text-gray-300 text-sm">
              Fastest Lap: <span className="text-white font-mono">{telemetry.session_info.fastest_driver}</span>
              {' '}&mdash;{' '}
              <span className="text-accent-cyan font-mono">{telemetry.session_info.fastest_time}</span>
              {' '}(Lap {telemetry.session_info.fastest_lap_number})
            </p>
          </div>

          <TrackMap drivers={telemetry.drivers} />
          <SpeedComparison drivers={telemetry.drivers} comparison={telemetry.speed_comparison} />
        </>
      )}
    </div>
  );
}
