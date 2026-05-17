import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useI18n } from '@/i18n'
import SettingsView from './SettingsView.vue'

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useI18n().setLocale('zh')
  })

  it('switches settings page header and back button copy with locale', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>chat</div>' } },
        { path: '/settings/subagents', component: { template: '<div>subagents</div>' } },
        { path: '/settings/users', component: { template: '<div>users</div>' } },
        { path: '/settings/personality', component: { template: '<div>personality</div>' } },
      ],
    })
    await router.push('/settings/subagents')
    await router.isReady()

    const wrapper = mount(SettingsView, {
      global: {
        plugins: [router],
        stubs: {
          RouterView: { template: '<div />' },
        },
      },
    })

    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('返回聊天')
    expect(wrapper.text()).toContain('子代理')
    expect(wrapper.text()).toContain('用户管理')
    expect(wrapper.text()).toContain('人格设置')

    useI18n().setLocale('en')
    await nextTick()

    expect(wrapper.text()).toContain('Settings')
    expect(wrapper.text()).toContain('Back to Chat')
    expect(wrapper.text()).toContain('Sub-Agents')
    expect(wrapper.text()).toContain('Users')
    expect(wrapper.text()).toContain('Personality')
  })
})
