# Task4 Router App Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 frontend 增加最小 `/login` 路由、认证守卫与 `App` 壳层切换，且只改 `router`、`App` 及对应测试。

**Architecture:** 复用现有 `auth` store 的 `isAuthenticated` 状态，不新增登录页面文件，而是在 `router` 中放置最小内联登录占位组件。通过路由 `meta.public`、`meta.requiresAuth` 与 `meta.shell` 统一驱动导航守卫和 `App.vue` 的 `DesktopShell` 包裹逻辑。

**Tech Stack:** Vue 3, Vue Router 4, Pinia, Vitest, Vue Test Utils, Vite

---

### Task 1: 路由守卫红绿测试

**Files:**
- Create: `frontend/src/router/index.spec.ts`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from './index'
import { useAuthStore } from '@/stores/auth'

describe('router auth guards', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const authStore = useAuthStore()
    authStore.$patch({
      isAuthenticated: false,
      user: null,
      apiKey: '',
    })
    await router.push('/login')
  })

  it('redirects anonymous users to /login for protected routes', async () => {
    await router.push('/memory')

    expect(router.currentRoute.value.fullPath).toBe('/login')
  })

  it('redirects authenticated users away from /login', async () => {
    const authStore = useAuthStore()
    authStore.$patch({
      isAuthenticated: true,
      user: {
        id: 'u1',
        username: 'alice',
        email: 'alice@example.com',
        role: 'user',
        created_at: '2026-05-17T09:00:00Z',
      },
      apiKey: 'key-123',
    })

    await router.push('/login')

    expect(router.currentRoute.value.fullPath).toBe('/')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/router/index.spec.ts`
Expected: FAIL，因为 `/login` 路由与前置守卫尚未实现。

- [ ] **Step 3: 做最小实现**

```ts
import { createRouter, createWebHistory } from 'vue-router'
import { h } from 'vue'
import { useAuthStore } from '@/stores/auth'

const LoginRouteView = {
  name: 'LoginRouteView',
  render: () => h('div', { class: 'login-route-placeholder' }, 'Login'),
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginRouteView,
      meta: {
        public: true,
        shell: false,
      },
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.public && authStore.isAuthenticated) {
    return '/'
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }

  return true
})
```

- [ ] **Step 4: 重新跑测试确认通过**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/router/index.spec.ts`
Expected: PASS

### Task 2: App 壳层切换红绿测试

**Files:**
- Create: `frontend/src/App.spec.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 写失败测试**

```ts
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import App from './App.vue'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    initAuth: vi.fn().mockResolvedValue(undefined),
  }),
}))

vi.mock('@/stores/settings', () => ({
  useSettingsStore: () => ({
    loadModels: vi.fn().mockResolvedValue(undefined),
  }),
}))

describe('App shell gating', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders route component without DesktopShell when shell meta is false', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: { template: '<div data-test="login-page">Login Page</div>' }, meta: { shell: false } },
      ],
    })
    await router.push('/login')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
        stubs: {
          DesktopShell: { template: '<div data-test="desktop-shell"><slot /></div>' },
        },
      },
    })

    expect(wrapper.find('[data-test="login-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="desktop-shell"]').exists()).toBe(false)
  })

  it('wraps route component in DesktopShell by default', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div data-test="home-page">Home Page</div>' }, meta: { shell: true } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
        stubs: {
          DesktopShell: { template: '<div data-test="desktop-shell"><slot /></div>' },
        },
      },
    })

    expect(wrapper.find('[data-test="home-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="desktop-shell"]').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/App.spec.ts`
Expected: FAIL，因为 `App.vue` 还会无条件包裹 `DesktopShell`。

- [ ] **Step 3: 做最小实现**

```vue
<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'

const route = useRoute()
const showShell = computed(() => route.meta.shell !== false)
</script>

<template>
  <RouterView v-else v-slot="{ Component }">
    <DesktopShell v-if="showShell">
      <component :is="Component" />
    </DesktopShell>
    <component :is="Component" v-else />
  </RouterView>
</template>
```

- [ ] **Step 4: 重新跑测试确认通过**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/App.spec.ts`
Expected: PASS

### Task 3: 回归验证

**Files:**
- Verify: `frontend/src/router/index.spec.ts`
- Verify: `frontend/src/App.spec.ts`
- Verify: `frontend/src/router/index.ts`
- Verify: `frontend/src/App.vue`

- [ ] **Step 1: 跑目标测试集**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/router/index.spec.ts src/App.spec.ts`
Expected: PASS

- [ ] **Step 2: 跑构建**

Run: `cd /Users/daobanxiang/myproject/TARS/frontend && npm run build`
Expected: PASS

- [ ] **Step 3: 自查**

检查本次改动文件中无 `console.log`、无 `TODO`、无调试残留；改动仅限 `router`、`App` 与对应测试。
