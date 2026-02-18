import { expect, test } from '@playwright/test';

test('admin login page renders', async ({ page }) => {
  await page.goto('/login');
  await expect(page.locator('input[name="username"]')).toBeVisible();
  await expect(page.locator('input[name="password"]')).toBeVisible();
  await expect(page.locator('button[type="submit"], input[type="submit"]')).toBeVisible();
});
