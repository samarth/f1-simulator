import { useState, useEffect, useRef, type ReactNode } from 'react';
import { fetchRaces, fetchYears } from '../api';
import type { RaceInfo } from '../types';
import { SessionContext } from './sessionContext';

export function SessionProvider({ children }: { children: ReactNode }) {
  const [year, setYear] = useState(0);
  const [race, setRace] = useState('');
  const [races, setRaces] = useState<RaceInfo[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [loadingRaces, setLoadingRaces] = useState(false);
  const [loadingYears, setLoadingYears] = useState(false);
  const [scheduleError, setScheduleError] = useState('');
  const initialRace = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingYears(true);
    fetchYears()
      .then((data) => {
        if (cancelled) return;
        const seasons = data.years;
        setYears(seasons);
        setScheduleError('');
        if (data.default_race) initialRace.current = data.default_race;
        const thisYear = new Date().getUTCFullYear();
        const preferred = data.default_year && seasons.includes(data.default_year)
          ? data.default_year
          : seasons.find((season) => season <= thisYear);
        if (preferred) {
          setYear((current) => (seasons.includes(current) && current !== 0 ? current : preferred));
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : 'Could not load seasons.';
        setScheduleError(message);
        setYears([]);
      })
      .finally(() => { if (!cancelled) setLoadingYears(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!year) return;
    let cancelled = false;
    setLoadingRaces(true);
    fetchRaces(year)
      .then((data) => {
        if (cancelled) return;
        setRaces(data);
        setScheduleError('');
        setRace((current) => {
          if (current && data.some((r) => r.name === current)) return current;
          const preferred = initialRace.current;
          if (preferred && data.some((r) => r.name === preferred)) {
            initialRace.current = null;
            return preferred;
          }
          const today = new Date().toISOString().slice(0, 10);
          const completed = data.filter((r) => r.date && r.date <= today);
          if (completed.length > 0) return completed[completed.length - 1].name;
          return data[0]?.name ?? '';
        });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : 'Could not load races.';
        setScheduleError(message);
        setRaces([]);
      })
      .finally(() => { if (!cancelled) setLoadingRaces(false); });
    return () => { cancelled = true; };
  }, [year]);

  return (
    <SessionContext.Provider
      value={{
        year,
        setYear,
        race,
        setRace,
        races,
        years,
        loadingRaces,
        loadingYears,
        scheduleError,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}
