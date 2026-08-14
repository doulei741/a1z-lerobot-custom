import { expect, test } from '@playwright/test'

test('all four workflows are reachable and mock mode is explicit', async ({ page }) => {
  await page.goto('/calibration')
  await expect(page.getByText('MOCK', { exact: true })).toBeVisible()
  for (const [label, title] of [
    ['遥控操作', '遥控操作'],
    ['数据录制', '数据录制'],
    ['模型推理', '模型推理'],
    ['机械臂校准', '机械臂校准'],
  ]) {
    await page.getByRole('link', { name: new RegExp(label) }).click()
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
  }
})

test('recording mock lifecycle rejects unsafe ordering and advances explicitly', async ({ page }) => {
  await page.goto('/recording')
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
  await expect(page.getByText(/SAVING|RESETTING/)).toBeVisible()
})
