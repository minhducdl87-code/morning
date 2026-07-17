const { test, expect } = require('@playwright/test');

test('production build loads its runtime data and briefing dashboard', async ({ page }) => {
  const failures = [];
  const isExternalFontUrl = rawUrl => {
    try {
      const hostname = new URL(rawUrl).hostname;
      return hostname === 'fonts.googleapis.com' || hostname === 'fonts.gstatic.com';
    } catch (_) {
      return false;
    }
  };
  page.on('console', message => {
    const locationUrl = message.location().url || '';
    if (message.type() === 'error' && !isExternalFontUrl(locationUrl) && !isExternalFontUrl(message.text())) {
      failures.push(`console: ${message.text()}`);
    }
  });
  page.on('pageerror', error => failures.push(`page: ${error.message}`));
  page.on('requestfailed', request => {
    if (!isExternalFontUrl(request.url())) failures.push(`request: ${request.url()}`);
  });
  page.on('response', response => {
    if (response.status() >= 400 && !isExternalFontUrl(response.url())) failures.push(`http ${response.status()}: ${response.url()}`);
  });

  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto('/');
  await expect(page.locator('.story-hero')).toBeVisible();
  await expect(page.locator('.story-card').first()).toBeVisible();
  await expect(page.locator('#archive-pane')).toBeVisible();
  await page.locator('.story-card').first().click();
  await expect(page.locator('#reader-pane')).toHaveClass(/open/);
  await expect(page.locator('#reader-pane h1')).toBeVisible();
  expect(failures).toEqual([]);
});
