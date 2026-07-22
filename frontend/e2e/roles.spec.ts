import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, type Locator, type Page, test, type TestInfo } from '@playwright/test'

const pageErrors = new WeakMap<Page, string[]>()
const releaseScreenshotDirectory = fileURLToPath(new URL('../../docs/screenshots/', import.meta.url))

test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  pageErrors.set(page, errors)
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text())
  })
})

test.afterEach(async ({ page }) => {
  expect(pageErrors.get(page)).toEqual([])
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
})

async function login(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(password)
  await page.getByRole('button', { name: '进入系统' }).click()
}

async function selectOption(page: Page, select: Locator, optionName: string): Promise<void> {
  await select.click()
  const listboxId = await select.getAttribute('aria-controls')
  expect(listboxId).not.toBeNull()
  await page.locator(`#${listboxId!}`).getByRole('option', { name: optionName, exact: true }).click()
}

async function expectCanvasPainted(page: Page): Promise<void> {
  const canvas = page.locator('canvas:visible').first()
  await expect(canvas).toBeVisible()
  await expect.poll(async () => canvas.evaluate(element => {
    const target = element as HTMLCanvasElement
    const context = target.getContext('2d')
    if (!context || !target.width || !target.height) return false
    const pixels = context.getImageData(0, 0, target.width, target.height).data
    let painted = 0
    let firstColor = -1
    let varied = false
    for (let index = 0; index < pixels.length; index += 64) {
      if (pixels[index + 3] === 0) continue
      painted += 1
      const color = (pixels[index] << 16) | (pixels[index + 1] << 8) | pixels[index + 2]
      if (firstColor < 0) firstColor = color
      else if (color !== firstColor) varied = true
    }
    return painted > 10 && varied
  })).toBe(true)
}

async function captureReleaseScreenshot(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  if (process.env.CAPTURE_RELEASE_SCREENSHOTS !== '1') return
  await mkdir(releaseScreenshotDirectory, { recursive: true })
  await page.screenshot({
    path: join(releaseScreenshotDirectory, `v1.2.0-${name}-${testInfo.project.name}.png`),
    fullPage: false,
    animations: 'disabled',
  })
}

test('student completes recommendation and feedback workflow', async ({ page, request }, testInfo) => {
  const teacherLogin = await request.post('/api/v1/auth/login', {
    data: { username: 'teacher01', password: 'Teacher@123456' },
  })
  expect(teacherLogin.ok()).toBeTruthy()
  const configResponse = await request.get('/api/v1/teacher/recommendation-config')
  expect(configResponse.ok()).toBeTruthy()
  const config = await configResponse.json()
  const { id: _id, ...originalConfig } = config
  void _id
  const stagedConfig = { ...originalConfig, min_path_length: 3, max_path_length: 3, mastery_threshold: 1 }
  expect((await request.put('/api/v1/teacher/recommendation-config', { data: stagedConfig })).ok()).toBeTruthy()

  try {
    await login(page, '20260001', 'Student@123456')
    await expect(page).toHaveURL(/\/student$/)
    await expect(page.getByRole('heading', { name: /学习画像/ })).toBeVisible()
    await expectCanvasPainted(page)

    const forbidden = await page.request.get('/api/v1/admin/users')
    expect(forbidden.status()).toBe(403)

    const dashboard = await page.request.get('/api/v1/students/me/dashboard')
    expect(dashboard.ok()).toBeTruthy()
    const dashboardData = await dashboard.json()
    const target = dashboardData.available_targets.find((item: { code: string }) => item.code === 'roc_auc')
    expect(target).toBeTruthy()
    await page.getByRole('combobox').click()
    await page.getByRole('option', { name: 'ROC与AUC · 难度3' }).click()
    await page.getByRole('button', { name: '生成路径' }).click()
    await expect(page.getByText(/完整必修依赖已拆分为/)).toBeVisible()
    expect(await page.locator('.path-stage').count()).toBeGreaterThan(1)
    await page.locator('.path-node').first().click()
    const nodeDialog = page.getByRole('dialog', { name: '知识点详情' })
    await expect(nodeDialog).toBeVisible()
    await nodeDialog.getByRole('button', { name: 'Close this dialog' }).click()
    await expect(nodeDialog).toBeHidden()
    await expect(page.locator('.el-message')).toHaveCount(0, { timeout: 5_000 })
    await captureReleaseScreenshot(page, testInfo, 'student-staged-path')
    const paths = await page.request.get('/api/v1/recommendations/me')
    expect(paths.ok()).toBeTruthy()
    const path = (await paths.json()).find((item: { target_knowledge_point_id: number }) => item.target_knowledge_point_id === target.id)
    expect(path.stage_count).toBeGreaterThan(1)
    expect(path.nodes.at(-1).knowledge_point_id).toBe(target.id)
    await page.locator('.path-node').first().click()
    await expect(nodeDialog).toBeVisible()
    const exerciseResponse = page.waitForResponse(response =>
      response.url().endsWith('/api/v1/students/me/behavior/exercises')
      && response.request().method() === 'POST',
    )
    await nodeDialog.getByRole('button', { name: '提交结果' }).click()
    const exerciseFeedback = await (await exerciseResponse).json()
    expect(exerciseFeedback.paths_marked_stale).toBeGreaterThanOrEqual(1)
    expect(exerciseFeedback.updated_path.id).not.toBe(path.id)
    expect(exerciseFeedback.updated_path.target_knowledge_point_id).toBe(target.id)
    expect(exerciseFeedback.updated_path.state).toBe('current')
    await expect(page.getByText('练习结果已保存，学习路径已自动更新')).toBeVisible()
    await expect(page.locator('.path-section .panel-heading')).toContainText(path.target_name)
  } finally {
    expect((await request.put('/api/v1/teacher/recommendation-config', { data: originalConfig })).ok()).toBeTruthy()
  }
})

test('teacher searches students, updates policy and manages a knowledge point', async ({ page }, testInfo) => {
  await login(page, 'teacher01', 'Teacher@123456')
  await expect(page).toHaveURL(/\/teacher$/)
  await expect(page.getByRole('heading', { name: '班级学情概览' })).toBeVisible()
  await expectCanvasPainted(page)

  await page.getByText('学生诊断', { exact: true }).click()
  await page.getByPlaceholder('姓名或学号').fill('20260001')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('20260001', { exact: true })).toBeVisible()
  const studentRow = page.getByRole('row').filter({ hasText: '20260001' })
  await studentRow.getByRole('button', { name: '详情' }).click()
  const diagnosisDialog = page.getByRole('dialog', { name: '学生01 · 诊断报告' })
  await expect(diagnosisDialog).toBeVisible()
  const viewport = page.viewportSize()
  expect(viewport).not.toBeNull()
  await expect.poll(async () => {
    const box = await diagnosisDialog.boundingBox()
    return Boolean(
      box && viewport
      && box.x >= -1
      && box.x + box.width <= viewport.width + 1
      && box.width >= Math.min(680, viewport.width) - 1,
    )
  }).toBe(true)
  await captureReleaseScreenshot(page, testInfo, 'teacher-diagnosis')
  await diagnosisDialog.getByRole('button', { name: 'Close this dialog' }).click()

  const configResponse = await page.request.get('/api/v1/teacher/recommendation-config')
  expect(configResponse.ok()).toBeTruthy()
  const config = await configResponse.json()
  const { id: _id, ...payload } = config
  void _id
  const update = await page.request.put('/api/v1/teacher/recommendation-config', { data: payload })
  expect(update.ok()).toBeTruthy()
  const recompute = await page.request.post('/api/v1/diagnosis/recompute', {
    params: { algorithm: config.diagnostic_algorithm },
  })
  expect(recompute.ok()).toBeTruthy()
  expect((await recompute.json()).algorithm).toBe(config.diagnostic_algorithm)

  const suffix = Date.now()
  const createdPoints: Array<{ id: number; name: string }> = []
  try {
    for (const [code, name] of [['prerequisite_a', '端到端前置甲'], ['prerequisite_b', '端到端前置乙'], ['target', '端到端目标']] as const) {
      const created = await page.request.post('/api/v1/knowledge/points', {
        data: {
          code: `e2e_${code}_${suffix}`,
          name: `${name}${suffix}`,
          chapter: '测试章节',
          dimension: 'statistics_foundation',
          difficulty: 1,
          resource_url: 'https://example.com/e2e',
          description: 'Playwright 关系 CRUD 验证',
        },
      })
      expect(created.status()).toBe(201)
      createdPoints.push(await created.json())
    }

    await page.getByText('知识图谱', { exact: true }).click()
    await expect(page.getByRole('heading', { name: '知识点与前置关系' })).toBeVisible()
    await page.getByText('前置关系', { exact: true }).click()
    await page.getByRole('button', { name: '添加关系' }).click()
    const addDialog = page.getByRole('dialog', { name: '添加前置关系' })
    const addSelects = addDialog.getByRole('combobox')
    await selectOption(page, addSelects.nth(0), createdPoints[0].name)
    await selectOption(page, addSelects.nth(1), createdPoints[2].name)
    await addDialog.getByRole('button', { name: '添加' }).click()

    let relationRow = page.getByRole('row').filter({ hasText: createdPoints[0].name }).filter({ hasText: createdPoints[2].name })
    await expect(relationRow).toBeVisible()
    await relationRow.getByRole('button', { name: '编辑关系' }).click()
    const editDialog = page.getByRole('dialog', { name: '编辑前置关系' })
    await selectOption(page, editDialog.getByRole('combobox').nth(0), createdPoints[1].name)
    await editDialog.getByRole('button', { name: '保存' }).click()

    relationRow = page.getByRole('row').filter({ hasText: createdPoints[1].name }).filter({ hasText: createdPoints[2].name })
    await expect(relationRow).toBeVisible()
    await relationRow.getByRole('button', { name: '删除关系' }).click()
    await page.getByRole('dialog', { name: '确认删除' }).getByRole('button', { name: '删除', exact: true }).click()
    await expect(relationRow).toHaveCount(0)
  } finally {
    for (const point of createdPoints.reverse()) {
      await page.request.delete(`/api/v1/knowledge/points/${point.id}?confirm=true`)
    }
  }
})

test('administrator opens account, knowledge and recommendation governance', async ({ page }, testInfo) => {
  await login(page, 'admin', 'Admin@123456')
  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByRole('heading', { name: '用户与教学组织' })).toBeVisible()
  await expect(page.getByText(/共 \d+ 个账号/)).toBeVisible()
  const configResponse = await page.request.get('/api/v1/teacher/recommendation-config')
  expect(configResponse.ok()).toBeTruthy()
  const config = await configResponse.json()
  const { id: _id, ...originalConfig } = config
  void _id
  try {
    await page.getByText('知识图谱', { exact: true }).click()
    await expect(page.getByRole('heading', { name: '知识点与前置关系' })).toBeVisible()
    await page.getByText('关系图', { exact: true }).click()
    await expectCanvasPainted(page)
    await captureReleaseScreenshot(page, testInfo, 'admin-knowledge-graph')
    await page.getByText('推荐策略', { exact: true }).click()
    await expect(page.getByRole('heading', { name: '推荐策略' })).toBeVisible()
    const updatedMaximum = config.max_path_length === 12 ? 11 : config.max_path_length + 1
    await page.getByRole('spinbutton').nth(1).fill(String(updatedMaximum))
    await page.getByRole('button', { name: '保存策略' }).click()
    await expect(page.getByText('推荐策略已保存，现有路径已标记为待更新')).toBeVisible()
    const saved = await page.request.get('/api/v1/teacher/recommendation-config')
    expect((await saved.json()).max_path_length).toBe(updatedMaximum)
  } finally {
    expect((await page.request.put('/api/v1/teacher/recommendation-config', { data: originalConfig })).ok()).toBeTruthy()
  }
})

test('administrator views, edits and deletes a multi-class teacher', async ({ page }) => {
  await login(page, 'admin', 'Admin@123456')
  await expect(page).toHaveURL(/\/admin$/)

  await page.getByRole('button', { name: '新增账号' }).click()
  const createDialog = page.getByRole('dialog', { name: '新增账号' })
  const initialPassword = createDialog.getByLabel('初始密码')
  await expect(initialPassword).toHaveValue('Student@123456')
  await createDialog.getByText('教师', { exact: true }).click()
  await expect(initialPassword).toHaveValue('Teacher@123456')
  await createDialog.getByText('管理员', { exact: true }).click()
  await expect(initialPassword).toHaveValue('Admin@123456')
  await createDialog.getByText('学生', { exact: true }).click()
  await expect(initialPassword).toHaveValue('Student@123456')
  await createDialog.getByRole('button', { name: '取消' }).click()

  const classesResponse = await page.request.get('/api/v1/admin/classes')
  expect(classesResponse.ok()).toBeTruthy()
  const classrooms = await classesResponse.json() as Array<{
    id: number
    grade_name: string
    name: string
  }>
  expect(classrooms.length).toBeGreaterThanOrEqual(2)

  const accountSuffix = Date.now()
  const displayName = `端到端教师${accountSuffix}`
  const teacherUsername = `e2e_teacher_${accountSuffix}`
  const created = await page.request.post('/api/v1/admin/users', {
    data: {
      username: teacherUsername,
      display_name: displayName,
      password: 'Teacher@123456',
      role: 'teacher',
      classroom_ids: [classrooms[0].id, classrooms[1].id],
    },
  })
  expect(created.status()).toBe(201)
  let teacherId: number | undefined = (await created.json()).id

  try {
    await page.reload()
    const teacherRow = page.getByRole('row').filter({ hasText: teacherUsername })
    await expect(teacherRow).toContainText(`${classrooms[0].grade_name} · ${classrooms[0].name}`)
    await expect(teacherRow).toContainText(`${classrooms[1].grade_name} · ${classrooms[1].name}`)
    await teacherRow.getByRole('button', { name: '详情' }).click()

    const drawer = page.getByRole('dialog', { name: new RegExp(`${displayName}.*用户详情`) })
    await expect(drawer).toBeVisible()
    await expect(drawer).toContainText(`${classrooms[0].grade_name} · ${classrooms[0].name}`)
    await expect(drawer).toContainText(`${classrooms[1].grade_name} · ${classrooms[1].name}`)
    await drawer.getByRole('button', { name: '编辑' }).click()
    await expect(drawer.getByLabel('角色')).toBeDisabled()
    const firstClassLabel = `${classrooms[0].grade_name} · ${classrooms[0].name}`
    await drawer.locator('.el-select__selection .el-tag')
      .filter({ hasText: firstClassLabel })
      .locator('.el-tag__close')
      .click()
    await drawer.getByRole('button', { name: '保存修改' }).click()
    await expect(page.getByText('用户信息已更新')).toBeVisible()
    await expect(drawer).not.toContainText(firstClassLabel)
    await expect(drawer).toContainText(`${classrooms[1].grade_name} · ${classrooms[1].name}`)

    await drawer.getByRole('button', { name: '删除用户' }).click()
    const deleteDialog = page.getByRole('dialog', { name: '确认删除用户' })
    await expect(deleteDialog).toContainText('此操作无法撤销')
    await deleteDialog.getByRole('button', { name: '删除', exact: true }).click()
    await expect(page.getByText('用户已删除')).toBeVisible()
    await expect(teacherRow).toHaveCount(0)
    teacherId = undefined
  } finally {
    if (teacherId) await page.request.delete(`/api/v1/admin/users/${teacherId}`)
  }
})
