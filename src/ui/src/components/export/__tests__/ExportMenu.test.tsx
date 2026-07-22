import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { postSessionExport, downloadBlob } from "../../../api/exportClient";
import { ExportMenu } from "../ExportMenu";

vi.mock("../../../api/exportClient", () => ({
  postSessionExport: vi.fn(),
  downloadBlob: vi.fn(),
}));

describe("ExportMenu", () => {
  it("shows friendly message when itinerary is not approved", () => {
    render(<ExportMenu sessionId="sess-1" approved={false} />);
    expect(screen.getByTestId("export-not-approved")).toHaveTextContent(
      "Finalize your itinerary",
    );
    expect(screen.queryByTestId("export-trigger")).not.toBeInTheDocument();
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
});
