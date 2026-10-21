import type {
  RaceInfo,
  DriverInfo,
  DegradationResponse,
  PitStats,
  ActualStrategy,
  SimulateResponse,
} from '../types';

const BASE = '/api';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function errorMessage(res: Response): Promise<string> {
  const body = await res.json().catch(() => ({}));
  const detail = body?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === 'string' ? item : item?.msg))
      .filter((item): item is string => Boolean(item));
    if (messages.length > 0) return messages.join(', ');
  }
  return res.statusText || 'Request failed';
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new ApiError(await errorMessage(res), res.status);
  }
  return res.json();
}

export async function fetchYears() {
  return fetchJson<{ years: number[]; default_year?: number | null; default_race?: string | null }>(
    `${BASE}/years`
  );
}

export async function fetchRaces(year: number) {
  const data = await fetchJson<{ year: number; races: RaceInfo[] }>(
    `${BASE}/races?year=${year}`
  );
  return data.races;
}

export async function fetchDrivers(year: number, race: string) {
  const data = await fetchJson<{ drivers: DriverInfo[] }>(
    `${BASE}/drivers?year=${year}&race=${encodeURIComponent(race)}`
  );
  return data.drivers;
}

export async function fetchDegradation(year: number, race: string): Promise<DegradationResponse> {
  return fetchJson<DegradationResponse>(
    `${BASE}/degradation?year=${year}&race=${encodeURIComponent(race)}`
  );
}

export async function fetchPitStats(year: number, race: string): Promise<PitStats> {
  return fetchJson<PitStats>(
    `${BASE}/pit-stats?year=${year}&race=${encodeURIComponent(race)}`
  );
}

export async function fetchActualStrategy(
  year: number,
  race: string,
  driver: string
): Promise<ActualStrategy> {
  return fetchJson<ActualStrategy>(
    `${BASE}/actual-strategy?year=${year}&race=${encodeURIComponent(race)}&driver=${driver}`
  );
}

export async function postSimulate(
  year: number,
  race: string,
  driver: string,
  stints: { compound: string; laps: number }[]
): Promise<SimulateResponse> {
  const res = await fetch(`${BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ year, race, driver, stints }),
  });
  if (!res.ok) {
    throw new ApiError(await errorMessage(res), res.status);
  }
  return res.json();
}
