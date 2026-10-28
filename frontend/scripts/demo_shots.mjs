// The nine demo screenshots at 1366x768 -> docs/screenshots/*-1366.png
//   dashboard, queue, hero_workspace (0417 compare), twin_search (0417 re-shot lab), land (0417), timeline (0422), forensics (0431), sources, evaluation
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
const shot = async (name) => { await page.screenshot({ path: `${out}${name}-1366.png` }); console.log('saved', name) }
const go = async (path, wait = 1500) => { await page.goto(base + path, { waitUntil: 'networkidle' }); await page.waitForTimeout(wait) }

async function compare(appId, findingText, name) {
  await go(`/workspace/${appId}`, 800)
  const card = page.locator('div.rounded-xl.border').filter({ hasText: findingText }).first()
  await card.getByText(findingText).first().click()
  await page.waitForTimeout(600)
  await card.getByText('Compare side by side').click()
  await page.waitForFunction(() => document.querySelectorAll('canvas').length >= 2, null, { timeout: 25000 })
  await page.waitForTimeout(6000)
  await shot(name)
}

await go('/'); await shot('dashboard')
await go('/queue'); await shot('queue')
await compare('EoA-DEMO-0417', 'Land area differs', 'hero_workspace')
const srcs = await (await fetch(base + '/api/twins/sources')).json()
const t = srcs.find((s) => s.application_id === 'EoA-DEMO-0417' && s.filename === 'Lab_Photo.jpg')
await go(`/twins?doc=${t.document_id}`, 7000); await shot('twin_search')
await compare('EoA-DEMO-0417', 'Same land parcel', 'land')
await compare('EoA-DEMO-0422', 'Fire NOC was issued', 'timeline')
await go('/forensics', 2500); await shot('forensics')
await go('/sources', 2000); await shot('sources')
await go('/evaluation', 2000); await shot('evaluation')
await browser.close()
