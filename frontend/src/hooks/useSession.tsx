import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { fetchRaces, fetchYears } from '../api';
import type { RaceInfo } from '../types';

interface SessionContextValue {
  year: number;
  setYear: (y: number) => void;
  race: string;
  setRace: (r: string) => void;
  session: string;
  setSession: (s: string) => void;
  races: RaceInfo[];
  years: number[];
  loadingRaces: boolean;
  loadingYears: boolean;
  scheduleError: string;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [year, setYear] = useState(0);
  const [race, setRace] = useState('');
  const [session, setSession] = useState('R');
  const [races, setRaces] = useState<RaceInfo[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [loadingRaces, setLoadingRaces] = useState(false);
  const [loadingYears, setLoadingYears] = useState(false);
  const [scheduleError, setScheduleError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoadingYears(true);
    fetchYears()
      .then((data) => {
        if (cancelled) return;
        setYears(data);
        setScheduleError('');
        if (data.length > 0) {
          setYear((current) => (data.includes(current) ? current : data[0]));
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : 'Could not load seasons.';
        setScheduleError(message);
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
          if (data.length > 0 && !data.some((r) => r.name === current)) {
            return data[0].name;
          }
          return current;
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
        session,
        setSession,
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

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
