/** Browser-console logging for Supervisor API traffic (debug / testing only). */

function timestamp(): string {
  return new Date().toISOString();
}

export function logApiRequest(
  method: string,
  url: string,
  body: unknown,
): void {
  console.info(`[${timestamp()}] Supervisor API → ${method} ${url}`, body);
}

export function logApiResponse(
  method: string,
  url: string,
  body: unknown,
  status = 200,
): void {
  console.info(`[${timestamp()}] Supervisor API ← ${status} ${method} ${url}`, body);
}

export function logApiError(
  method: string,
  url: string,
  error: unknown,
): void {
  console.error(`[${timestamp()}] Supervisor API ✕ ${method} ${url}`, error);
}
