/** Browser-console logging for Supervisor API traffic (development only). */

const devLoggingEnabled = import.meta.env.DEV;

function timestamp(): string {
  return new Date().toISOString();
}

export function logApiRequest(
  method: string,
  url: string,
  body: unknown,
): void {
  if (!devLoggingEnabled) {
    return;
  }
  console.info(`[${timestamp()}] Supervisor API → ${method} ${url}`, body);
}

export function logApiResponse(
  method: string,
  url: string,
  body: unknown,
  status = 200,
): void {
  if (!devLoggingEnabled) {
    return;
  }
  console.info(`[${timestamp()}] Supervisor API ← ${status} ${method} ${url}`, body);
}

export function logApiError(
  method: string,
  url: string,
  error: unknown,
): void {
  if (!devLoggingEnabled) {
    return;
  }
  console.error(`[${timestamp()}] Supervisor API ✕ ${method} ${url}`, error);
}
