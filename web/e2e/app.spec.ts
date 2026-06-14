import { test, expect } from '@playwright/test'

/**
 * Live smoke of all four pages against `fc26 serve` (real SPA + real API + real
 * DB). Assertions are data-resilient — they check structure and non-empty
 * results, never specific player names (the DB drifts under enrichment).
 */

test('root redirects to Cards and the sidebar has four nav links', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/cards$/)
  for (const label of ['Cards', 'Squads', 'Build', 'Upgrade']) {
    await expect(page.getByRole('link', { name: label })).toBeVisible()
  }
})

test('Cards page renders a non-empty grid from the real API', async ({ page }) => {
  await page.goto('/cards')
  // the "<n> cards" count line only appears once the query resolves
  await expect(page.getByText(/\b[1-9]\d* cards\b/)).toBeVisible({ timeout: 15_000 })
})

test('Cards search box accepts input and keeps the grid alive', async ({ page }) => {
  await page.goto('/cards')
  await expect(page.getByText(/\b[1-9]\d* cards\b/)).toBeVisible({ timeout: 15_000 })
  await page.getByPlaceholder(/search/i).fill('a')
  // debounced refetch resolves to a (possibly different) count without error
  await expect(page.getByText(/\b\d+ cards\b/)).toBeVisible({ timeout: 15_000 })
})

test('Build page builds an XI from the real API', async ({ page }) => {
  await page.goto('/build')
  await page.getByLabel(/budget/i).fill('300K')
  await page.getByRole('button', { name: /^build$/i }).click()
  // the Save-squad control only renders once a build result comes back
  await expect(page.getByRole('button', { name: /save squad/i })).toBeVisible({ timeout: 30_000 })
})

test('Squads page lists saved squads and loads one onto the pitch', async ({ page }) => {
  await page.goto('/squads')
  const squad = page.getByRole('button', { name: 'sample-rivals' })
  await expect(squad).toBeVisible({ timeout: 15_000 })
  await squad.click()
  // the side panel's empty-state appears once the squad+pitch render
  await expect(page.getByText(/click a player to see details/i)).toBeVisible({ timeout: 15_000 })
})

test('Upgrade page finds upgrades (or reports none) for a real squad', async ({ page }) => {
  await page.goto('/upgrade')
  await page.getByLabel(/squad/i).selectOption('sample-rivals')
  await page.getByLabel(/budget/i).fill('200K')
  await page.getByRole('button', { name: /find upgrades/i }).click()
  await expect(
    page.getByText(/swaps? found|no upgrades found/i),
  ).toBeVisible({ timeout: 30_000 })
})
