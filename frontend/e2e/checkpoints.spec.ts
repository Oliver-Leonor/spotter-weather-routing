import { expect, test } from '@playwright/test'
import { runDemoTrip } from './support.ts'

test('selecting a route and a checkpoint shows the weather behind its risk', async ({ page }) => {
  await runDemoTrip(page)

  await page.getByRole('button', { name: 'Route A', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Route A', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )

  const routeA = page.getByRole('article').filter({ hasText: 'Route A' })
  await routeA.getByRole('button', { name: 'Mile 375, No Travel' }).click()

  const details = page.getByRole('region', { name: 'Checkpoint details' })
  await expect(details.getByRole('heading', { name: 'Route A, mile 375' })).toBeVisible()
  await expect(details).toBeInViewport()
  await expect(details.getByText('Risk at estimated arrival')).toBeVisible()
  await expect(details.getByRole('row', { name: /Wind 50.1 mph No Travel/ })).toBeVisible()
  await expect(
    details.getByText('Wind of 45 to 55 mph is No Travel with a load over 30,000 lb.'),
  ).toBeVisible()
  await expect(details.getByText('Fri, Nov 6, 2:27 PM CST')).toBeVisible() // local time there

  await details.getByRole('button', { name: 'Next checkpoint' }).click()
  await expect(details.getByRole('heading', { name: 'Route A, mile 400' })).toBeVisible()
  await details.getByRole('button', { name: 'Close checkpoint details' }).click()
  await expect(details).toHaveCount(0)
})

test('checkpoint details can be opened and stepped through with the keyboard alone', async ({
  page,
}) => {
  await runDemoTrip(page)

  await page.getByRole('button', { name: 'Route B', exact: true }).focus()
  await page.keyboard.press('Tab') // into Route B's risk ribbon: one tab stop
  await expect(page.getByRole('button', { name: 'Origin, Low' }).nth(1)).toBeFocused()
  await page.keyboard.press('End')
  await page.keyboard.press('ArrowLeft')
  await page.keyboard.press('Enter')

  const details = page.getByRole('region', { name: 'Checkpoint details' })
  await expect(details.getByRole('heading', { name: 'Route B, mile 600' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Route B', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )

  await page.keyboard.press('Tab') // leaves the ribbon instead of walking every checkpoint
  await expect(page.getByRole('button', { name: 'Route C', exact: true })).toBeFocused()
})
