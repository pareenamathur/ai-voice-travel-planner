import { describe, expect, it } from "vitest";

import { inferLoadingHint, loadingHintMessage } from "../loadingHint";

describe("loadingHint", () => {
  it("detects recommendation requests", () => {
    expect(inferLoadingHint("Suggest good food places in Jaipur")).toBe("recommend");
    expect(loadingHintMessage("recommend")).toBe("Finding recommendations…");
  });

  it("detects edit requests", () => {
    expect(inferLoadingHint("Add shopping on Day 3")).toBe("edit");
    expect(loadingHintMessage("edit")).toBe("Updating your itinerary…");
  });
});
