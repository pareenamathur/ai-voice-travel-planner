import { useCallback, useEffect, useRef, useState } from "react";

import {
  downloadBlob,
  postSessionExport,
  postSessionExportEmail,
  type ExportFormat,
} from "../../api/exportClient";
import { SupervisorApiError } from "../../api/supervisorClient";

import "./export.css";

const NOT_APPROVED_MESSAGE =
  "Finalize your itinerary to export PDF, Markdown, or JSON.";

export interface ExportMenuProps {
  sessionId: string | null;
  approved: boolean;
}

type ToastState = { kind: "success" | "error"; message: string } | null;

const FORMAT_LABELS: Record<ExportFormat, string> = {
  pdf: "PDF",
  markdown: "Markdown",
  json: "JSON",
};

export function ExportMenu({ sessionId, approved }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [toast, setToast] = useState<ToastState>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onDocClick = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const runExport = useCallback(
    async (format: ExportFormat) => {
      setOpen(false);
      if (!approved) {
        setToast({ kind: "error", message: NOT_APPROVED_MESSAGE });
        return;
      }
      if (!sessionId) {
        setToast({ kind: "error", message: "Start a trip before exporting." });
        return;
      }
      setDownloadLoading(true);
      try {
        const { blob, filename } = await postSessionExport({
          session_id: sessionId,
          format,
        });
        downloadBlob(blob, filename);
        setToast({
          kind: "success",
          message: `${FORMAT_LABELS[format]} download started.`,
        });
      } catch (error) {
        const message =
          error instanceof SupervisorApiError
            ? error.message
            : "Export failed. Please try again.";
        setToast({ kind: "error", message });
      } finally {
        setDownloadLoading(false);
      }
    },
    [approved, sessionId],
  );

  const runEmailExport = useCallback(async () => {
    if (!approved) {
      setToast({ kind: "error", message: NOT_APPROVED_MESSAGE });
      return;
    }
    if (!sessionId) {
      setToast({ kind: "error", message: "Start a trip before exporting." });
      return;
    }
    const trimmed = email.trim();
    if (!trimmed) {
      setToast({ kind: "error", message: "Enter an email address." });
      return;
    }

    setEmailLoading(true);
    try {
      const result = await postSessionExportEmail({
        session_id: sessionId,
        email: trimmed,
      });
      setToast({
        kind: "success",
        message: result.message || "Itinerary emailed successfully.",
      });
    } catch (error) {
      const message =
        error instanceof SupervisorApiError
          ? error.message
          : "Email export failed. Please try again.";
      setToast({ kind: "error", message });
    } finally {
      setEmailLoading(false);
    }
  }, [approved, email, sessionId]);

  if (!approved) {
    return (
      <p className="export-hint" data-testid="export-not-approved">
        {NOT_APPROVED_MESSAGE}
      </p>
    );
  }

  const busy = downloadLoading || emailLoading;

  return (
    <div className="export-menu" ref={menuRef} data-testid="export-menu">
      <div className="export-menu__actions">
        <button
          type="button"
          className="export-menu__trigger"
          aria-haspopup="menu"
          aria-expanded={open}
          disabled={busy || !sessionId}
          onClick={() => setOpen((value) => !value)}
          data-testid="export-trigger"
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            download
          </span>
          {downloadLoading ? "Exporting…" : "Export"}
        </button>

        {open ? (
          <ul className="export-menu__dropdown" role="menu">
            {(["pdf", "markdown", "json"] as ExportFormat[]).map((format) => (
              <li key={format} role="none">
                <button
                  type="button"
                  role="menuitem"
                  className="export-menu__option"
                  onClick={() => void runExport(format)}
                  data-testid={`export-format-${format}`}
                >
                  {FORMAT_LABELS[format]}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="export-menu__email" data-testid="export-email-row">
        <input
          type="email"
          className="export-menu__email-input"
          placeholder="Email address"
          value={email}
          disabled={busy || !sessionId}
          onChange={(event) => setEmail(event.target.value)}
          data-testid="export-email-input"
        />
        <button
          type="button"
          className="export-menu__email-btn"
          disabled={busy || !sessionId}
          onClick={() => void runEmailExport()}
          data-testid="export-email-submit"
        >
          {emailLoading ? "Sending…" : "Email PDF"}
        </button>
      </div>

      {toast ? (
        <p
          className={`export-toast export-toast--${toast.kind}`}
          role="status"
          data-testid="export-toast"
        >
          {toast.message}
        </p>
      ) : null}
    </div>
  );
}
