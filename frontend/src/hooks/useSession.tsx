import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { fetchRaces } from '../api';
import type { RaceInfo } from '../types';

interface SessionContextValue {
  year: number;
  setYear: (y: number) => void;
  race: string;
  setRace: (r: string) => void;
  session: string;
  setSession: (s: string) => void;
  races: RaceInfo[];
  loadingRaces: boolean;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [year, setYear] = useState(2024);
  const [race, setRace] = useState('');
  const [session, setSession] = useState('R');
  const [races, setRaces] = useState<RaceInfo[]>([]);
  const [loadingRaces, setLoadingRaces] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoadingRaces(true);
    fetchRaces(year)
      .then((data) => {
        if (cancelled) return;
        setRaces(data);
        if (data.length > 0 && !data.some((r) => r.name === race)) {
          setRace(data[0].name);
        }
      })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoadingRaces(false); });
    return () => { cancelled = true; };
  }, [year]);

  return (
    <SessionContext.Provider
      value={{ year, setYear, race, setRace, session, setSession, races, loadingRaces }}
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
