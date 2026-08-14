import { chromium } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

const taskId = process.argv[2]
const screenshot = process.argv[3] ?? '/tmp/a1z-three-camera-preview.png'
if (!taskId) {
  console.error('Usage: node scripts/verify-camera-preview-browser.mjs <task-id> [screenshot.png]')
  process.exit(2)
}

const browser = await chromium.launch({ headless: process.env.HEADED !== '1' })
try {
  console.log('browser-started')
  const page = await browser.newPage({ viewport: { width: 1800, height: 1080 } })
  await page.addInitScript(({ activeTaskId }) => {
    localStorage.setItem('a1z-web-active-task', JSON.stringify({
      state: { activeTaskId, activeTaskType: 'camera_preview', lastSeq: 0 },
      version: 0,
    }))
  }, { activeTaskId: taskId })
  // The application intentionally keeps a WebSocket open, so networkidle is
  // not a valid readiness signal here.
  await page.goto('http://127.0.0.1:5173/teleoperation', { waitUntil: 'domcontentloaded' })
  console.log('teleoperation-page-loaded')
  const viewer = page.getByTitle('Rerun 实时相机画面')
  await viewer.waitFor({ state: 'visible', timeout: 10_000 })
  console.log('rerun-iframe-visible')
  const source = await viewer.getAttribute('src')
  if (!source?.includes('?url=rerun%2Bhttp')) {
    throw new Error(`Rerun iframe is missing its gRPC source: ${source}`)
  }
  await page.waitForTimeout(8_000)
  if (process.env.HEADED === '1') {
    const holdSeconds = Number(process.env.HOLD_SECONDS ?? 60)
    await page.bringToFront()
    console.log(JSON.stringify({ taskId, source, mode: 'headed', holdSeconds }))
    await page.waitForTimeout(holdSeconds * 1_000)
  } else {
    // Rerun continuously repaints a WebGL canvas. Playwright's high-level
    // screenshot can wait forever for that surface to settle, whereas CDP
    // captures the currently presented browser frame immediately.
    const cdp = await page.context().newCDPSession(page)
    const capture = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
    await writeFile(screenshot, Buffer.from(capture.data, 'base64'))
    console.log(JSON.stringify({ taskId, source, screenshot }))
  }
} finally {
  await browser.close()
}
