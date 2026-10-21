import type {ApiError, DecodeResponse} from './types';

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ?? 'http://localhost:8000';

export class DecodeError extends Error {
  readonly payload: ApiError;

  constructor(payload: ApiError) {
    super(payload.message);
    this.payload = payload;
  }
}

/** VIN decodieren. Wirft DecodeError mit maschinenlesbarem Code. */
export async function decodeVin(vin: string, lang: string): Promise<DecodeResponse> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api/v1/decode`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({vin, lang}),
      cache: 'no-store'
    });
  } catch {
    throw new DecodeError({code: 'network', message: 'API unreachable', detail: {}});
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    if (body && typeof body === 'object' && 'error' in body) {
      throw new DecodeError((body as {error: ApiError}).error);
    }
    throw new DecodeError({code: 'network', message: 'Unexpected response', detail: {}});
  }

  return body as DecodeResponse;
}

export const apiDocsUrl = `${BASE_URL}/docs`;
