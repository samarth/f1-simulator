import type {
  RaceInfo,
  DriverInfo,
  TelemetryResponse,
  DegradationResponse,
  PitStats,
  ActualStrategy,
  SimulateResponse,
} from '../types';

const BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

export async function fetchRaces(year: number) {
  const data = await fetchJson<{ year: number; races: RaceInfo[] }>(
    `${BASE}/races?year=${year}`
  );
  return data.races;
}

export async function fetchDrivers(year: number, race: string, session: string) {
  const data = await fetchJson<{ drivers: DriverInfo[] }>(
    `${BASE}/drivers?year=${year}&race=${encodeURIComponent(race)}&session=${session}`
  );
  return data.drivers;
}

export async function fetchTelemetry(
  year: number,
  race: string,
  session: string,
  drivers: string[]
): Promise<TelemetryResponse> {
  return fetchJson<TelemetryResponse>(
    `${BASE}/telemetry?year=${year}&race=${encodeURIComponent(race)}&session=${session}&drivers=${drivers.join(',')}`
  );
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
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}
