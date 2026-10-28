// Visits every sidebar page at 1366x768: reports empty states, console errors and horizontal overflow; saves 4 screenshots.
import { chromium } from '@playwright/test'

const base = process.argv[2] ?? 'http://localhost:5173'
const out = new URL('../../docs/screenshots/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const pages = [['/', 'dashboard'], ['/queue', 'queue'], ['/workspace', 'workspace'], ['/twins', 'twins'], ['/forensics', 'forensics'], ['/sources', 'sources'],
  ['/rules', 'rules'], ['/audit', 'audit'], ['/evaluation', 'evaluation'], ['/self-check', 'self-check']]
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
const errors = []
page.on('pageerror', (e) => errors.push(e.message.slice(0, 120)))
page.on('console', (m) => m.type() === 'error' && !/Failed to load resource/.test(m.text()) && errors.push(m.text().slice(0, 120)))
page.on('response', (r) => r.status() >= 400 && errors.push(`${r.status()} ${r.url().replace(base, '')}`))
let bad = 0
for (const [route, name] of pages) {
  errors.length = 0
  await page.goto(base + route, { waitUntil: 'networkidle' })
  await page.waitForTimeout(route === '/twins' ? 6000 : 1800)
  if (name === 'audit') { await page.getByText('Verify integrity').click(); await page.waitForTimeout(700) }
  const r = await page.evaluate(() => ({
    empty: document.querySelectorAll('main svg.lucide-inbox').length,
    hOverflow: Math.max(document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth, (document.querySelector('main')?.scrollWidth ?? 0) - (document.querySelector('main')?.clientWidth ?? 0)),
    title: document.querySelector('main h1')?.textContent,
  }))
  const flag = r.empty || r.hOverflow > 0 || errors.length
  if (flag) bad++
  console.log(`${route.padEnd(12)} h1="${r.title}" empty=${r.empty} overflow=${r.hOverflow}px errors=${errors.length ? errors.join(' | ') : 'none'} ${flag ? '<-- CHECK' : 'ok'}`)
  if (['forensics', 'sources', 'rules', 'audit'].includes(name)) await page.screenshot({ path: `${out}${name}-1366.png` })
}
await browser.close()
console.log(bad ? `${bad} page(s) need attention` : 'All pages ok')
