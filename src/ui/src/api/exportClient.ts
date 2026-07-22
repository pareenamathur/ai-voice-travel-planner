/** POST /api/session/export — download approved itinerary file. */

import { logApiError, logApiRequest } from "./apiLogger";
import { getApiBaseUrl, SupervisorApiError, parseError } from "./supervisorClient";

export type ExportFormat = "pdf" | "markdown" | "json";

export interface SessionExportRequest {
  session_id: string;
  format: ExportFormat;
}

export async function postSessionExport(
  request: SessionExportRequest,
): Promise<{ blob: Blob; filename: string }> {
  const url = `${getApiBaseUrl()}/api/session/export`;
  logApiRequest("POST", url, request);

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await parseError(response);
    logApiError("POST", url, { status: response.status, message: error.message });
    throw error;
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/i.exec(disposition);
  const filename = match?.[1] ?? `itinerary.${request.format === "markdown" ? "md" : request.format}`;
  const blob = await response.blob();
  return { blob, filename };
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
