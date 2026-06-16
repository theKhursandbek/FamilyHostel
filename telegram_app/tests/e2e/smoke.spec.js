// @ts-check
import { test, expect } from "@playwright/test";

/**
 * Smoke tests for the Telegram Mini App.
 *
 * These run against the production preview build (`vite preview`) and
 * exercise the public surface that does NOT require Telegram initData
 * — so we can validate routing, theme bootstrap and that the React tree
 * renders without uncaught errors on a real mobile viewport.
 */

test.describe("Mini App smoke", () => {
  test("home page loads and mounts the React tree", async ({ page }) => {
    /** @type {string[]} */
    const errors = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/");
    // The PWA manifest should be linked.
    const manifestHref = await page.locator('link[rel="manifest"]').getAttribute("href");
    expect(manifestHref).toBe("/manifest.webmanifest");

    // Wait for the React app to mount (root has children).
    await expect(page.locator("#root > *")).toBeVisible();

    // No uncaught JS errors.
    expect(errors).toEqual([]);
  });

  test("login page is reachable", async ({ page }) => {
    await page.goto("/login");
    // Fallback dev login button (only present when VITE_DEV_FALLBACK_LOGIN=true).
    // We don't strictly require it, but the page should at least render.
    await expect(page.locator("#root > *")).toBeVisible();
  });

  test("bottom navigation renders", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("nav.bottom-nav")).toBeVisible();
  });
});
