import { describe, expect, it } from "vitest";

import {
  looksLikeConfirmation,
  shouldShowConfirmRejectedWarning,
} from "../debugHelpers";

describe("debugHelpers", () => {
  it("recognizes common affirmative confirmations", () => {
    expect(looksLikeConfirmation("yes")).toBe(true);
    expect(looksLikeConfirmation("Yes please")).toBe(true);
    expect(looksLikeConfirmation("yeah")).toBe(true);
  });

  it("rejects non-confirmations", () => {
    expect(looksLikeConfirmation("Plan 2 days in Jaipur")).toBe(false);
    expect(looksLikeConfirmation("yes but change the city")).toBe(false);
  });

  it("warns when affirmation gets confirm intent again", () => {
    expect(shouldShowConfirmRejectedWarning("yes", "confirm")).toBe(true);
    expect(shouldShowConfirmRejectedWarning("yes", "plan")).toBe(false);
    expect(shouldShowConfirmRejectedWarning("Plan Jaipur", "confirm")).toBe(false);
  });
});
