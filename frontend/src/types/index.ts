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

export interface WeatherData {
  available: boolean;
  air_temp: number | null;
  track_temp: number | null;
  humidity: number | null;
  rainfall: boolean;
  wind_speed: number | null;
  conditions: string;
  track_temp_min: number | null;
  track_temp_max: number | null;
}

export interface FuelEffect {
  laps: number[];
  fuel_penalty_seconds: number[];
  fuel_effect_per_lap: number;
  total_fuel_effect: number;
  description: string;
}

export interface DegradationResponse {
  compounds: Record<string, CompoundDegradation>;
  models: Record<string, DegradationModel>;
  weather: WeatherData;
  fuel_effect: FuelEffect;
  total_laps: number;
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

export interface StintAnalysis {
  stint: number;
  compound: string;
  laps: number;
  delta: number;
  explanation: string;
}

export interface SuggestedStrategy {
  label: string;
  stints: { compound: string; laps: number }[];
  total_time: number;
  delta_vs_actual: number;
}

export interface SimulateResponse {
  simulated_laps: SimulatedLap[];
  user_total_time: number;
  actual: ActualStrategy | null;
  cumulative_gap: CumulativeGapPoint[];
  stint_analysis: StintAnalysis[];
  suggested_strategies: SuggestedStrategy[];
}

export interface StintInput {
  compound: string;
  laps: number | '';
}
