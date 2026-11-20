import { createContext, useContext } from 'react';
import type { RaceInfo } from '../types';

export interface SessionContextValue {
  year: number;
  setYear: (y: number) => void;
  race: string;
  setRace: (r: string) => void;
  races: RaceInfo[];
  years: number[];
  loadingRaces: boolean;
  loadingYears: boolean;
  scheduleError: string;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
