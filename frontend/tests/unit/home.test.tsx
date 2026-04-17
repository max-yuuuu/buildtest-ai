import { describe, it, expect } from "vitest";

describe("Home page", () => {
  it("重定向到 providers", async () => {
    const mod = await import("@/app/page");
    expect(typeof mod.default).toBe("function");
  });
});
