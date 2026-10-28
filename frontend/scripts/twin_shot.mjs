// twin_search-1366.png from the bare /twins route (checks the default is EoA-DEMO-0417's re-shot lab photo); also a Copied-filter check
import { chromium } from '@playwright/test'

const base = process.argv[2] ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
await page.goto(base + '/twins', { waitUntil: 'networkidle' })
await page.waitForSelector('img[alt="matched keypoints"]', { timeout: 30000 })
await page.waitForTimeout(5000)
console.log('default selection:', await page.locator('main select').inputValue(), '|', (await page.locator('main select option:checked').textContent())?.trim())
await page.screenshot({ path: `${out}twin_search-1366.png` })
console.log('saved twin_search')
await page.getByRole('button', { name: /^Copied/ }).click()
await page.waitForSelector('img[alt="matched keypoints"]', { timeout: 30000 })
await page.waitForTimeout(4000)
console.log('Copied filter ->', (await page.locator('main select option:checked').textContent())?.trim(), '|', await page.locator('span.rounded-full').first().textContent())
await page.screenshot({ path: 'C:/Users/harsh/AppData/Local/Temp/claude/c--sih26261/e6b6316c-a073-47b5-b41b-cc243a71f03e/scratchpad/twin_copied.png' })
await browser.close()
