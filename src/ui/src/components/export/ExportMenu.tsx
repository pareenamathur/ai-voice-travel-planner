import { useCallback, useEffect, useRef, useState } from "react";

import {
  downloadBlob,
  postSessionExport,
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
  const [loading, setLoading] = useState(false);
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
      setLoading(true);
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
        setLoading(false);
      }
    },
    [approved, sessionId],
  );

  if (!approved) {
    return (
      <p className="export-hint" data-testid="export-not-approved">
        {NOT_APPROVED_MESSAGE}
      </p>
    );
  }

  return (
    <div className="export-menu" ref={menuRef} data-testid="export-menu">
      <button
        type="button"
        className="export-menu__trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={loading || !sessionId}
        onClick={() => setOpen((value) => !value)}
        data-testid="export-trigger"
      >
        <span className="material-symbols-outlined" aria-hidden="true">
          download
        </span>
        {loading ? "Exporting…" : "Export"}
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
