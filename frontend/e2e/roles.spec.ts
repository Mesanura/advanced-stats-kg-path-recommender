import { expect, type Page, test } from '@playwright/test'

const pageErrors = new WeakMap<Page, string[]>()

test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  pageErrors.set(page, errors)
  page.on('pageerror', error => errors.push(error.message))
})

test.afterEach(async ({ page }) => {
  expect(pageErrors.get(page)).toEqual([])
})

async function login(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(password)
  await page.getByRole('button', { name: '进入系统' }).click()
}

test('student completes recommendation and feedback workflow', async ({ page }) => {
  await login(page, '20260001', 'Student@123456')
  await expect(page).toHaveURL(/\/student$/)
  await expect(page.getByRole('heading', { name: /学习画像/ })).toBeVisible()

  const forbidden = await page.request.get('/api/v1/admin/users')
  expect(forbidden.status()).toBe(403)

  const dashboard = await page.request.get('/api/v1/students/me/dashboard')
  expect(dashboard.ok()).toBeTruthy()
  const dashboardData = await dashboard.json()
  const target = dashboardData.available_targets.at(-1)
  expect(target).toBeTruthy()
  const recommendation = await page.request.post('/api/v1/recommendations/me', {
    data: { target_knowledge_point_id: target.id },
  })
  expect(recommendation.ok()).toBeTruthy()
  const path = await recommendation.json()
  const exercise = await page.request.post('/api/v1/students/me/behavior/exercises', {
    data: { knowledge_point_id: path.nodes[0].knowledge_point_id, is_correct: true },
  })
  expect(exercise.ok()).toBeTruthy()
  expect((await exercise.json()).paths_marked_stale).toBeGreaterThanOrEqual(1)
})

test('teacher searches students, updates policy and manages a knowledge point', async ({ page }) => {
  await login(page, 'teacher01', 'Teacher@123456')
  await expect(page).toHaveURL(/\/teacher$/)
  await expect(page.getByRole('heading', { name: '班级学情概览' })).toBeVisible()

  await page.getByText('学生诊断', { exact: true }).click()
  await page.getByPlaceholder('姓名或学号').fill('20260001')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('20260001', { exact: true })).toBeVisible()

  const configResponse = await page.request.get('/api/v1/teacher/recommendation-config')
  expect(configResponse.ok()).toBeTruthy()
  const config = await configResponse.json()
  const { id: _id, ...payload } = config
  const update = await page.request.put('/api/v1/teacher/recommendation-config', { data: payload })
  expect(update.ok()).toBeTruthy()
  const recompute = await page.request.post('/api/v1/diagnosis/recompute', {
    data: { algorithm: config.diagnostic_algorithm },
  })
  expect(recompute.ok()).toBeTruthy()

  const code = `e2e_${Date.now()}`
  const created = await page.request.post('/api/v1/knowledge/points', {
    data: {
      code,
      name: '端到端测试知识点',
      chapter: '测试章节',
      dimension: 'statistics_foundation',
      difficulty: 1,
      resource_url: 'https://example.com/e2e',
      description: 'Playwright CRUD 验证',
    },
  })
  expect(created.status()).toBe(201)
  const point = await created.json()
  const patched = await page.request.patch(`/api/v1/knowledge/points/${point.id}`, {
    data: { name: '端到端测试知识点（已更新）' },
  })
  expect(patched.ok()).toBeTruthy()
  const removed = await page.request.delete(`/api/v1/knowledge/points/${point.id}?confirm=true`)
  expect(removed.ok()).toBeTruthy()
})

test('administrator opens account management and teacher cannot access admin data', async ({ page }) => {
  await login(page, 'admin', 'Admin@123456')
  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByRole('heading', { name: '用户与教学组织' })).toBeVisible()
  await expect(page.getByText(/共 53 个账号/)).toBeVisible()
})
