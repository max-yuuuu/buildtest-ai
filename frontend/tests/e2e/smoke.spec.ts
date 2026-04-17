import { test, expect } from "@playwright/test";

test("首页可访问且显示平台名", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /BuildTest AI/i })).toBeVisible();
});
