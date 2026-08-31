import { expect, test } from '@playwright/test'

const EMAIL = 'admin@company.com'
const PASSWORD = 'Admin@2026'

test.describe('登录与全局导航', () => {
  test('登录页渲染并支持账号密码登录', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByText('欢迎回来')).toBeVisible()
    await page.getByPlaceholder('name@company.com').fill(EMAIL)
    await page.getByPlaceholder('输入密码').fill(PASSWORD)
    await page.getByRole('button', { name: /登录工作空间/ }).click()
    await expect(page).toHaveURL(/\/projects$/)
    await expect(page.getByText('项目空间')).toBeVisible()
  })

  test('登录后左侧导航可访问全部管理页面', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('name@company.com').fill(EMAIL)
    await page.getByPlaceholder('输入密码').fill(PASSWORD)
    await page.getByRole('button', { name: /登录工作空间/ }).click()
    await expect(page).toHaveURL(/\/projects$/)

    const targets = [
      ['智能体管理', /agent-types$/],
      ['Skill 管理与装配', /skills$/],
      ['开发流程编排', /pipeline-templates$/],
      ['用户与权限', /users$/],
      ['模型与 API 配置', /settings$/],
      ['资源与运行监控', /resources$/],
    ] as const
    for (const [label, pattern] of targets) {
      await page.getByRole('link', { name: new RegExp(label) }).click()
      await expect(page).toHaveURL(pattern)
    }
  })

  test('未登录访问受保护页面重定向到登录页', async ({ page }) => {
    await page.goto('/projects')
    await expect(page).toHaveURL(/\/login\?redirect=/)
  })
})
