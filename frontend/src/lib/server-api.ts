import type {
  BrandSummary,
  DecodeResponse,
  GenerationSummary,
  GenerationVehicle,
  ModelSummary,
  VehicleDetail,
  VehicleMatch
} from './types';

/**
 * Serverseitige Aufrufe der eigenen API.
 *
 * Im Container erreicht das Frontend die API unter ihrem Dienstnamen, der
 * Browser dagegen unter der oeffentlichen Adresse. Deshalb gibt es zwei
 * Variablen; ohne die interne faellt es auf die oeffentliche zurueck.
 */
const INTERNAL_BASE = (
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  'http://localhost:8000'
).replace(/\/$/, '');

async function getJson<T>(path: string, revalidate = 300): Promise<T | null> {
  try {
    const response = await fetch(`${INTERNAL_BASE}${path}`, {
      next: {revalidate},
      headers: {Accept: 'application/json'}
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/** Vollstaendige Decodierung inklusive Trefferliste. */
export function decodeVinOnServer(vin: string, lang: string) {
  return getJson<DecodeResponse>(
    `/api/v1/decode/${encodeURIComponent(vin)}?lang=${lang}`
  );
}

/** Nur die Trefferliste - fuer Praefix-Suchen ab 10 Zeichen. */
export function fetchMatches(vin: string) {
  return getJson<VehicleMatch[]>(`/api/v1/vehicles/${encodeURIComponent(vin)}`);
}

/**
 * Technische Daten einer einzelnen Typengenehmigung.
 *
 * Die VIN wird mitgegeben, weil eine Genehmigung mehrere Ausfuehrungen
 * abdeckt: mit ihr laesst sich aus "Radstand 3106-3216 mm" der Wert
 * dieses Fahrzeugs bestimmen.
 */
export function fetchVehicle(id: string | number, vin?: string) {
  const query = vin ? `?vin=${encodeURIComponent(vin)}` : '';
  return getJson<VehicleDetail>(
    `/api/v1/vehicle/${encodeURIComponent(String(id))}${query}`
  );
}

export type RecentLookup = {
  vin_masked: string;
  make: string | null;
  model: string | null;
  model_year: number | null;
  requested_at: string;
};

export type ModelYearCode = {code: string; years: number[]};

export type CountryRange = {
  range: string;
  country: string;
  country_code: string | null;
  region_code: string | null;
  region: string;
};

/** Zuletzt gesuchte Fahrzeuge (maskiert) fuer die Startseite. */
export function fetchRecent(limit = 10) {
  return getJson<RecentLookup[]>(`/api/v1/recent?limit=${limit}`, 60);
}

/** Modelljahr-Codes - aus derselben Konstante wie der Decoder. */
export function fetchModelYears() {
  return getJson<ModelYearCode[]>('/api/v1/reference/model-years', 86400);
}

/** Laenderbereiche der WMI nach ISO 3780. */
export function fetchCountryRanges() {
  return getJson<CountryRange[]>('/api/v1/reference/countries', 86400);
}

/** Alle Marken des Bestands, haeufigste zuerst. */
export function fetchBrands() {
  return getJson<BrandSummary[]>('/api/v1/brands', 300);
}

/** Modelle einer Marke. */
export function fetchBrandModels(brand: string) {
  return getJson<ModelSummary[]>(`/api/v1/brands/${encodeURIComponent(brand)}`, 300);
}

/** Baureihen eines Modells. */
export function fetchModelGenerations(brand: string, model: string) {
  return getJson<GenerationSummary[]>(
    `/api/v1/brands/${encodeURIComponent(brand)}/${encodeURIComponent(model)}`,
    300
  );
}

/** Fahrzeuge einer Baureihe. */
export function fetchGenerationVehicles(
  brand: string,
  model: string,
  generation: string
) {
  return getJson<GenerationVehicle[]>(
    `/api/v1/brands/${encodeURIComponent(brand)}/${encodeURIComponent(model)}/` +
      `${encodeURIComponent(generation)}`,
    300
  );
}
