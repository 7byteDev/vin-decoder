export type FieldResult = {
  value: string | number | null;
  confidence: number;
  sources: string[];
  value_i18n?: Record<string, string> | null;
  alternatives: {value: string | number; confidence: number; sources: string[]}[];
  conflict: boolean;
};

export type VinStructure = {
  wmi: string;
  vds: string;
  vis_masked: string;
  extended_wmi: string | null;
  is_small_manufacturer: boolean;
  region_code: string | null;
  region_name: string | null;
  country: string | null;
  country_code: string | null;
  in_primary_focus: boolean;
  check_digit: string | null;
  check_digit_expected: string | null;
  check_digit_valid: boolean | null;
  check_digit_required: boolean;
  model_year_code: string | null;
  model_year: number | null;
  model_year_candidates: number[];
  plant_code: string | null;
};

export type DecodeResponse = {
  vin_masked: string;
  status: 'ok' | 'partial';
  confidence: number;
  structure: VinStructure;
  fields: Record<string, FieldResult>;
  conflicts: string[];
  warnings: string[];
  sources_used: string[];
  provider_errors: Record<string, string>;
  duration_ms: number;
  matches: VehicleMatch[];
  match_count: number;
};

export type ApiError = {
  code: string;
  message: string;
  detail: {characters?: string[]; suggestion?: string | null; length?: number};
};

export type VehicleMatch = {
  id: number;
  approval_number: string | null;
  make: string | null;
  model: string | null;
  variant: string | null;
  year: number | null;
  body_form: string | null;
  fuel_type: string | null;
  displacement_ccm: number | null;
  power_kw: number | null;
  power_ps: number | null;
  transmission: string | null;
  gears: number | null;
  drive_type: string | null;
  doors: number | null;
  seats: number | null;
  match_quality: number;
  matched_prefix: string | null;
};

export type SpecSection = {
  key: string;
  label: string;
  entries: Record<string, string>;
};

export type VehicleDetail = {
  id: number;
  approval_number: string | null;
  approval_date: string | null;
  eu_approval_number: string | null;
  vin_patterns: string[];
  make: string | null;
  model: string | null;
  variant: string | null;
  manufacturer: string | null;
  vehicle_kind: string | null;
  vehicle_class: string | null;
  body_form: string | null;
  engine_make: string | null;
  engine_model: string | null;
  engine_code: string | null;
  fuel_type: string | null;
  displacement_ccm: number | null;
  power_kw: number | null;
  power_ps: number | null;
  power_rpm: number | null;
  torque_nm: number | null;
  torque_rpm: number | null;
  drive_type: string | null;
  transmission: string | null;
  gears: number | null;
  doors: number | null;
  seats_total: number | null;
  top_speed_kmh: number | null;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
  wheelbase_mm: number | null;
  weight_kg: number | null;
  max_weight_kg: number | null;
  variant_code: string | null;
  ranges: Record<string, number>;
  sections: SpecSection[];
  logo: BrandLogo | null;
  images: VehicleImage[];
  consumption: ConsumptionRow[];
  emissions: EmissionRow[];
  source: string | null;
  attribution: string | null;
};

export type BrandLogo = {
  url: string;
  page_url: string | null;
  license: string | null;
  license_url: string | null;
  author: string | null;
};

export type VehicleImage = {
  file_key: string;
  url: string;
  thumb_url: string;
  page_url: string | null;
  license: string | null;
  license_url: string | null;
  author: string | null;
  description: string | null;
  width: number | null;
  height: number | null;
};

export type ConsumptionRow = {
  fuel_type: string | null;
  transmission: string | null;
  efficiency_category: string | null;
  consumption_l100: number | null;
  co2_g_km: number | null;
  consumption_wltp_l100: number | null;
  co2_wltp_g_km: number | null;
  electric_kwh100: number | null;
  electric_range_km: number | null;
};

export type EmissionRow = {
  fuel_type: string | null;
  transmission: string | null;
  emission_code: string | null;
  exhaust_code: string | null;
  cylinders: number | null;
  displacement_ccm: number | null;
  power_kw: number | null;
  pollutants: Record<string, string>;
};

export type BrandSummary = {
  make: string;
  name: string;
  slug: string;
  vehicles: number;
  models: number;
  logo_url: string | null;
};

export type ModelSummary = {
  model: string;
  slug: string;
  generations: number;
  vehicles: number;
  year_from: number | null;
  year_to: number | null;
  thumb_url: string | null;
};

export type GenerationSummary = {
  platform: string;
  slug: string;
  year_from: number | null;
  year_to: number | null;
  vehicles: number;
  image_url: string | null;
  thumb_url: string | null;
};

export type GenerationVehicle = {
  id: number;
  model: string;
  fuel_type: string | null;
  power_kw: number | null;
  power_ps: number | null;
  displacement_ccm: number | null;
  transmission: string | null;
  gears: number | null;
  drive_type: string | null;
  body_form: string | null;
  doors: number | null;
  year_from: number | null;
  year_to: number | null;
  approvals: number;
  approval_numbers: string[];
};
