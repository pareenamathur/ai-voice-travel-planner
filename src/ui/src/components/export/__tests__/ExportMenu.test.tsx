import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  postSessionExport,
  postSessionExportEmail,
  downloadBlob,
} from "../../../api/exportClient";
import { ExportMenu } from "../ExportMenu";

vi.mock("../../../api/exportClient", () => ({
  postSessionExport: vi.fn(),
  postSessionExportEmail: vi.fn(),
  downloadBlob: vi.fn(),
}));

describe("ExportMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows friendly message when itinerary is not approved", () => {
    render(<ExportMenu sessionId="sess-1" approved={false} />);
    expect(screen.getByTestId("export-not-approved")).toHaveTextContent(
      "Finalize your itinerary",
    );
    expect(screen.queryByTestId("export-trigger")).not.toBeInTheDocument();
    expect(screen.queryByTestId("export-email-row")).not.toBeInTheDocument();
  });

  it("renders export dropdown when approved", async () => {
    vi.mocked(postSessionExport).mockResolvedValue({
      blob: new Blob(["# Trip"], { type: "text/markdown" }),
      filename: "jaipur-itinerary.md",
    });

    render(<ExportMenu sessionId="sess-1" approved />);
    fireEvent.click(screen.getByTestId("export-trigger"));
    fireEvent.click(screen.getByTestId("export-format-markdown"));

    await waitFor(() => {
      expect(postSessionExport).toHaveBeenCalledWith({
        session_id: "sess-1",
        format: "markdown",
      });
    });
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled());
    expect(await screen.findByTestId("export-toast")).toHaveTextContent(
      "Markdown download started",
    );
  });

  it("emails PDF when approved and email is provided", async () => {
    vi.mocked(postSessionExportEmail).mockResolvedValue({
      success: true,
      message: "Itinerary emailed successfully",
    });

    render(<ExportMenu sessionId="sess-1" approved />);
    fireEvent.change(screen.getByTestId("export-email-input"), {
      target: { value: "traveler@example.com" },
    });
    fireEvent.click(screen.getByTestId("export-email-submit"));

    await waitFor(() => {
      expect(postSessionExportEmail).toHaveBeenCalledWith({
        session_id: "sess-1",
        email: "traveler@example.com",
      });
    });
    expect(await screen.findByTestId("export-toast")).toHaveTextContent(
      "Itinerary emailed successfully",
    );
  });

  it("shows error when email is missing", async () => {
    render(<ExportMenu sessionId="sess-1" approved />);
    fireEvent.click(screen.getByTestId("export-email-submit"));

    expect(postSessionExportEmail).not.toHaveBeenCalled();
    expect(await screen.findByTestId("export-toast")).toHaveTextContent(
      "Enter an email address",
    );
  });
});
