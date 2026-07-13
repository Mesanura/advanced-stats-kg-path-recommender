import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import App from './App.vue'
import HomeView from './views/HomeView.vue'

describe('App', () => {
  it('renders the application title', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: HomeView }],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router, ElementPlus] } })
    expect(wrapper.text()).toContain('课程知识图谱学习路径推荐系统')
  })
})
