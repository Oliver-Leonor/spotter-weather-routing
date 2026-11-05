import { expect, test, type Page } from '@playwright/test'
import {
  horizontalOverflow,
  mapIsIdle,
  mapPicture,
  recordRequests,
  runDemoTrip,
} from './support.ts'

const slider = (page: Page) => page.getByRole('slider', { name: 'Corridor forecast time' })

test('the forecast slider repaints the corridor without any network request', async ({ page }) => {
  await runDemoTrip(page)
  const corridor = page.getByRole('region', { name: 'Corridor forecast' })
  await expect(slider(page)).toHaveValue('0')
  await expect(corridor.getByText('Fri, Nov 6, 8:00 AM MST')).toBeVisible()
  await expect(corridor.getByText('At departure')).toBeVisible()

  const atDeparture = await mapPicture(page)
  const requests = recordRequests(page)

  await slider(page).fill('6') // the demo storm is at its peak six hours after departure
  await expect(corridor.getByText('Fri, Nov 6, 2:00 PM MST')).toBeVisible()
  await expect(corridor.getByText('6 h after departure')).toBeVisible()
  await mapIsIdle(page)
  const atStorm = await mapPicture(page)

  await slider(page).fill('48')
  await expect(corridor.getByText('Sun, Nov 8, 8:00 AM MST')).toBeVisible()
  await mapIsIdle(page)

  const twoDaysLater = await mapPicture(page)

  expect(atStorm.equals(atDeparture)).toBe(false) // the storm cells are shaded differently
  expect(twoDaysLater.equals(atDeparture)).toBe(true) // calm again: the same picture as at departure
  expect(requests.map((request) => request.url())).toEqual([]) // and nothing was fetched
})

test('the slider works from the keyboard and announces the time', async ({ page }) => {
  await runDemoTrip(page)

  await slider(page).focus()
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowRight')
  await expect(slider(page)).toHaveValue('3')
  await expect(slider(page)).toHaveAttribute(
    'aria-valuetext',
    'Fri, Nov 6, 11:00 AM MST, 3 h after departure',
  )
  await page.keyboard.press('End')
  await expect(slider(page)).toHaveValue('48')
  await page.keyboard.press('Home')
  await expect(slider(page)).toHaveValue('0')
})

test('the weather corridor can be switched off and on', async ({ page }) => {
  await runDemoTrip(page)
  await slider(page).fill('6')
  await mapIsIdle(page)
  const withCorridor = await mapPicture(page)

  await page.getByRole('checkbox', { name: 'Weather corridor' }).uncheck()
  await mapIsIdle(page)
  const withoutCorridor = await mapPicture(page)
  expect(withoutCorridor.equals(withCorridor)).toBe(false)

  await page.getByRole('checkbox', { name: 'Weather corridor' }).check()
  await mapIsIdle(page)
  expect((await mapPicture(page)).equals(withCorridor)).toBe(true)
})

test('a new comparison starts the forecast at the departure hour again', async ({ page }) => {
  await runDemoTrip(page)
  await slider(page).fill('30')
  await expect(slider(page)).toHaveValue('30')

  await page.getByRole('button', { name: 'Compare routes' }).click()
  await expect(page.getByRole('heading', { name: 'Take Route C' })).toBeVisible()
  await expect(slider(page)).toHaveValue('0')
  expect(await horizontalOverflow(page)).toBe(0)
})
