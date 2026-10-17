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
  observed?: boolean;
  sample_laps?: number;
  delta?: number;
  typical_life?: number;
  field_relative?: boolean;
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
  source?: string;
  fuel_corrected?: boolean;
}

export interface ModelInfo {
  observed_compounds: string[];
  unmodeled_compounds: string[];
  pace_note: string;
  fuel_source: string;
  fuel_corrected: boolean;
  wet: boolean;
  min_compounds: number;
  neutral_laps: number;
}

export interface DegradationResponse {
  compounds: Record<string, CompoundDegradation>;
  models: Record<string, DegradationModel>;
  weather: WeatherData;
  fuel_effect: FuelEffect;
  total_laps: number;
  model_info?: ModelInfo;
}

export interface PitStats {
  avg_pit_time: number;
  min_pit_time: number;
  max_pit_time: number;
  num_stops: number;
  source?: string;
}

export interface ModelFit {
  replay_time: number;
  actual_time: number;
  residual_seconds: number;
  residual_per_lap: number;
  timed_laps: number;
  green_rmse: number | null;
  driver_offset: number;
  pit_loss: number;
  pit_source: string;
  note: string;
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
  model_fit?: ModelFit | null;
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
  model_fit?: ModelFit | null;
}

export interface StintInput {
  compound: string;
  laps: number | '';
}
