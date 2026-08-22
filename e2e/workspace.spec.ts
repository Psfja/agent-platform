import { expect, test } from '@playwright/test'

const EMAIL = 'admin@company.com'
const PASSWORD = 'Admin@2026'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByPlaceholder('name@company.com').fill(EMAIL)
  await page.getByPlaceholder('输入密码').fill(PASSWORD)
  await page.getByRole('button', { name: /登录工作空间/ }).click()
  await expect(page).toHaveURL(/\/projects$/)
}

test.describe('项目管理与 Agent 运行时', () => {
  test('项目列表展示真实数据并可进入仪表盘', async ({ page }) => {
    await login(page)
    const firstProject = page.locator('.project-card, [class*="project-card"]').first()
    await firstProject.click()
    await expect(page).toHaveURL(/\/projects\/[a-z-]+$/)
    await expect(page.locator('.project-hero-card')).toBeVisible()
  })

  test('Agent 运行时：记忆、Skills、沙箱与对话标签', async ({ page }) => {
    await login(page)
    await page.goto('/projects/leave-hub/runtime')
    await expect(page.getByText('持久记忆', { exact: false }).first()).toBeVisible()
    // Skills 注册表（真实后端数据）
    await page.getByRole('button', { name: /Skill 注册表/ }).click()
    await expect(page.locator('.runtime-skill-card').first()).toBeVisible()
    // 沙箱执行
    await page.getByRole('button', { name: /沙箱执行/ }).click()
    await page.getByRole('button', { name: '运行代码' }).click()
    await expect(page.locator('.sandbox-runs').getByText('Python 代码').first()).toBeVisible({ timeout: 20_000 })
  })

  test('流程编排：流程图编辑器与 AI 生成入口', async ({ page }) => {
    await login(page)
    await page.goto('/admin/pipeline-templates')
    await expect(page.getByText('AI 生成流程')).toBeVisible()
    await page.getByRole('button', { name: '手动创建' }).click()
    await expect(page.getByText('流程编排编辑器')).toBeVisible()
    await page.getByRole('button', { name: '添加节点' }).click()
    await expect(page.locator('.flow-node-group').first()).toBeVisible()
  })
})
