import { expect, test } from '@playwright/test'

// Smoke test against a real docker-compose stack running with OFFLINE=true
// (deterministic fake providers end to end, no API keys, real ffmpeg).
// Run docker compose up --build -d first; see README's "Running the UI".
test('creates an offline job, watches it complete, and plays the result', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByText('OFFLINE mode', { exact: false })).toBeVisible()

  await page.getByLabel("What's it about?", { exact: false }).fill('a short e2e smoke test topic')
  await page.getByRole('button', { name: 'Create video' }).click()

  await page.waitForURL(/\/jobs\/.+/, { timeout: 15_000 })

  // The assembly stage finishing is what makes the Result section (and the
  // video element) appear; wait for that rather than any "completed" text,
  // since earlier stages report "completed" on their own cards first.
  await expect(page.getByRole('heading', { name: 'Result' })).toBeVisible({ timeout: 120_000 })

  // Matched by src rather than a generic `video` locator: the scene
  // gallery alongside it may also render <video> thumbnails for
  // ai_video/stock_video scenes.
  const video = page.locator('video[src*="final.mp4"]')
  await expect(video).toBeVisible()
})
