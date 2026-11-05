import { expect, test } from '@playwright/test'
import { horizontalOverflow, mockBackend, runDemoTrip } from './support.ts'

test('demo trip shows three routes, the recommendation and a persistent simulated-weather label', async ({
  page,
}) => {
  await runDemoTrip(page)

  await expect(page.getByRole('article')).toHaveCount(3)
  const recommended = page.getByRole('article').filter({ hasText: 'Route C' })
  await expect(recommended.getByText('Recommended')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Route C', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(
    page.getByRole('article').filter({ hasText: 'Route A' }).getByText('Blocked'),
  ).toBeVisible()

  const label = page.getByRole('note', { name: 'Simulated weather' })
  await expect(label).toContainText('This is demo data, not a real forecast')
  await page.mouse.wheel(0, 2000)
  await expect(label).toBeInViewport() // it stays on screen while the page scrolls
  expect(await horizontalOverflow(page)).toBe(0)
})

test('a typed trip is sent with the chosen places, load and interval', async ({ page }) => {
  const backend = await mockBackend(page)
  await page.goto('/')

  await page.getByRole('combobox', { name: 'Origin' }).fill('Denver')
  await page.getByRole('option', { name: 'Denver, Colorado, US' }).click()
  await page.getByRole('combobox', { name: 'Destination' }).fill('Kansas')
  await page.getByRole('option', { name: 'Kansas City, Missouri, US' }).click()
  await page.getByLabel('Load weight').fill('45000')
  await page.getByText('50 mi', { exact: true }).click()
  await page.getByRole('button', { name: 'Compare routes' }).click()

  await expect(page.getByRole('heading', { name: 'Take Route C' })).toBeVisible()
  expect(backend.analyses).toHaveLength(1)
  expect(backend.analyses[0]).toMatchObject({
    origin: { lat: 39.73915, lon: -104.9847, label: 'Denver, Colorado, US' },
    destination: { lat: 39.09973, lon: -94.57857, label: 'Kansas City, Missouri, US' },
    load_weight_lb: 45000,
    checkpoint_interval_miles: 50,
    mode: 'live',
  })
  expect(backend.analyses[0].departure_time).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\.000Z$/)
})

test('a lighter load changes the result', async ({ page }) => {
  const backend = await runDemoTrip(page)
  await expect(page.getByRole('status').filter({ hasText: 'Take Route C' })).toContainText(
    'only route that is neither blocked nor unverified',
  )

  await page.getByLabel('Load weight').fill('28000')
  await page.getByRole('button', { name: 'Compare routes' }).click()

  await expect(page.getByRole('status').filter({ hasText: 'Take Route C' })).toContainText(
    'avoids 50.0 miles of severe weather encountered on Route B',
  )
  await expect(page.getByText('Blocked')).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Analyzed trip' })).toContainText('28,000 lb load')
  expect(backend.analyses.map((body) => body.load_weight_lb)).toEqual([42000, 28000])
  expect(backend.analyses[1].mode).toBe('fixture') // still the demo trip
})

test('a provider failure is explained, clears the old result and can be retried', async ({
  page,
}) => {
  const backend = await runDemoTrip(page)
  backend.failNext(502, {
    code: 'ROUTING_UNAVAILABLE',
    message: 'The routing service is unavailable right now. Please try again shortly.',
    provider: 'valhalla',
  })

  await page.getByRole('button', { name: 'Compare routes' }).click()

  const alert = page.getByRole('alert')
  await expect(alert).toContainText('The routing service is unavailable right now.')
  await expect(page.getByRole('article')).toHaveCount(0)
  await expect(page.getByRole('note', { name: 'Simulated weather' })).toHaveCount(0)

  await alert.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { name: 'Take Route C' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('the form explains what is missing before anything is sent', async ({ page }) => {
  const backend = await mockBackend(page)
  await page.goto('/')
  await page.getByLabel('Load weight').fill('250000')
  await page.getByRole('button', { name: 'Compare routes' }).click()

  await expect(page.getByText('Choose where the trip starts.')).toBeVisible()
  await expect(page.getByText('Choose where the trip ends.')).toBeVisible()
  await expect(page.getByText('Load weight must be between 0 and 200,000 lb.')).toBeVisible()
  expect(backend.analyses).toHaveLength(0)
})
