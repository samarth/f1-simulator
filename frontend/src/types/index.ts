export interface RaceInfo {
  round: number;
  name: string;
  country: string;
  date: string;
}

export interface DriverInfo {
  code: string;
  name: string;
  team: string;
}

export interface TrackPoint {
  x: number;
  y: number;
  speed: number;
}

export interface SpeedPoint {
  distance: number;
  speed: number;
}

export interface DriverTelemetry {
  driver: string;
  lap_time: string;
  lap_number: number;
  color: string;
  track: TrackPoint[];
  speed: SpeedPoint[];
}

export interface SpeedComparisonPoint {
  distance: number;
  speeds: Record<string, number>;
}

export interface SessionInfo {
  fastest_driver: string;
  fastest_time: string;
  fastest_lap_number: number;
}

export interface TelemetryResponse {
  session_info: SessionInfo;
  drivers: DriverTelemetry[];
  speed_comparison: SpeedComparisonPoint[];
}

export interface CompoundDegradation {
  tyre_life: number[];
  avg_lap_time: number[];
  std_lap_time: number[];
  count: number[];
}

export interface DegradationModel {
  base_time: number;
  deg_rate: number;
}

export interface DegradationResponse {
  compounds: Record<string, CompoundDegradation>;
  models: Record<string, DegradationModel>;
}

export interface PitStats {
  avg_pit_time: number;
  min_pit_time: number;
  max_pit_time: number;
  num_stops: number;
}

export interface StintInfo {
  stint: number;
  compound: string;
  start_lap: number;
  end_lap: number;
  laps: number;
}

export interface LapTime {
  lap: number;
  time_sec: number;
  compound: string;
  tyre_life: number;
}

export interface PitLap {
  lap: number;
  from_compound: string;
  to_compound: string;
}

export interface ActualStrategy {
  stints: StintInfo[];
  lap_times: LapTime[];
  total_time: number;
  pit_laps: PitLap[];
  total_laps: number;
}

export interface SimulatedLap {
  lap: number;
  time_sec: number;
  compound: string;
  tyre_life: number;
  is_pit_lap: boolean;
}

export interface CumulativeGapPoint {
  lap: number;
  gap: number;
}

export interface SimulateResponse {
  simulated_laps: SimulatedLap[];
  user_total_time: number;
  actual: ActualStrategy | null;
  cumulative_gap: CumulativeGapPoint[];
}

export interface StintInput {
  compound: string;
  laps: number | '';
}
