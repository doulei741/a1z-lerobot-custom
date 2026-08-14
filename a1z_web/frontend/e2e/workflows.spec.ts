import { expect, test } from '@playwright/test'

test('all four workflows are reachable and mock mode is explicit', async ({ page }) => {
  await page.goto('/calibration')
  await expect(page.locator('body')).toHaveCSS('overflow-y', 'hidden')
  await expect(page.getByRole('main')).toHaveCSS('overflow-y', 'hidden')
  await expect(page.getByText('MOCK', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '设备中心' }).click()
  await expect(page.getByRole('heading', { name: '设备准备中心' })).toBeVisible()
  await expect(page.getByText('Mock 设备清单')).toBeVisible()
  await page.getByRole('button', { name: '关闭设备中心' }).click()
  for (const [label, title] of [
    ['遥控操作', '遥控操作'],
    ['数据录制', '数据录制'],
    ['模型推理', '模型推理'],
    ['机械臂校准', '机械臂校准'],
  ]) {
    await page.getByRole('link', { name: new RegExp(label) }).click()
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
    await expect(page.getByRole('main')).toHaveCSS('overflow-y', 'hidden')
  }
})

test('recording mock lifecycle rejects unsafe ordering and advances explicitly', async ({ page }) => {
  await page.goto('/recording')
  await expect(page.locator('.record-config')).toHaveCSS('overflow-y', 'auto')
  const viewport = await page.evaluate(() => ({
    bodyHeight: document.body.getBoundingClientRect().height,
    viewportHeight: window.innerHeight,
    configClientHeight: document.querySelector<HTMLElement>('.record-config')!.clientHeight,
    configScrollHeight: document.querySelector<HTMLElement>('.record-config')!.scrollHeight,
  }))
  expect(viewport.bodyHeight).toBeLessThanOrEqual(viewport.viewportHeight)
  expect(viewport.configScrollHeight).toBeGreaterThan(viewport.configClientHeight)
  await page.getByRole('button', { name: '检查 Dataset Compatibility' }).click()
  await expect(page.getByText('COMPATIBLE')).toBeVisible()
  await page.getByLabel('确认录制安全检查').check()
  await page.getByRole('button', { name: '开始录制任务' }).click()
  await expect(page.getByRole('heading', { name: '当前运行在 Mock 仿真模式' })).toBeVisible()
  await page.getByRole('button', { name: '继续 Mock 仿真' }).click()
  await expect(page.getByRole('main').getByText('READY', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '开始本轮 Episode' }).click()
  await expect(page.getByRole('main').getByText('RECORDING', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '模拟一帧' }).click()
  await page.getByRole('button', { name: '提前结束并保存' }).click()
  await expect(page.getByRole('main').getByText('RESETTING', { exact: true })).toBeVisible()

  // Manual path: save, confirm reset, then explicitly start the next episode.
  await page.getByRole('button', { name: '重置完成' }).click()
  await expect(page.getByRole('main').getByText('READY', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '开始本轮 Episode' }).click()
  await page.getByRole('button', { name: '模拟一帧' }).click()

  // Quick Next path: save first, then start only after reset is confirmed.
  await page.getByRole('button', { name: '快速开始下一轮' }).click()
  await expect(page.getByRole('main').getByText('RESETTING', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '重置完成' }).click()
  await expect(page.getByRole('main').getByText('RECORDING', { exact: true })).toBeVisible()

  await expect(page.getByRole('button', { name: '正常停止整个任务' })).toBeEnabled()
  await page.getByRole('button', { name: '正常停止整个任务' }).click()
  await expect(page.getByRole('button', { name: '开始录制任务' })).toBeEnabled()
})
