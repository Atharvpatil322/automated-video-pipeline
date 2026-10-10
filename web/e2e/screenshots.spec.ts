import { expect, test } from '@playwright/test'

// Not part of the regular suite - a one-off capture for the phase 7
// write-up, run manually against the live OFFLINE compose stack.
test('capture home, mid-run, and finished job screenshots', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('OFFLINE mode', { exact: false })).toBeVisible()
  await page.screenshot({ path: 'screenshots/01-home.png', fullPage: true })

  await page.getByLabel("What's it about?", { exact: false }).fill('the history of lighthouses')
  await page.getByRole('button', { name: 'Create video' }).click()
  await page.waitForURL(/\/jobs\/.+/, { timeout: 15_000 })

  await expect(page.getByText('running', { exact: true }).first()).toBeVisible({
    timeout: 15_000,
  })
  // The elapsed-time clock is just an icon + mm:ss text (no "Elapsed:"
  // label) - wait for it via its role="timer"-free text pattern instead.
  await expect(page.getByText(/^\d+:\d{2}$/)).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: 'screenshots/02-job-mid-run.png', fullPage: true })

  await expect(page.getByRole('heading', { name: 'Result' })).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('video[src*="final.mp4"]')).toBeVisible()
  await page.screenshot({ path: 'screenshots/03-job-finished.png', fullPage: true })
})
