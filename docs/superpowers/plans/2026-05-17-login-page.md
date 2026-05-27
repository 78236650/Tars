---
doc_type: plan
status: shipped
platform_version: 4.0.0
catalog: docs/superpowers/README.md
---
# Login Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a branded login page for TARS with account-based sign-in, inline workspace join affordances, auth-aware routing, and the minimum backend credential support needed to make it real.

**Architecture:** Keep the existing API key session model as the runtime credential, but add username/email + password authentication on the backend through a new login endpoint that returns the existing API key after verifying the password. On the frontend, gate workspace routes behind auth, render the new login page outside `DesktopShell`, and evolve the current `auth` store instead of creating a second auth stack. Because admin-created users currently have no password, extend the user creation flow to set an initial password so the new login path is actually usable.

**Tech Stack:** FastAPI, SQLite, Python standard-library hashing (`hashlib.pbkdf2_hmac`), Vue 3, Pinia, Vue Router, Vitest, Vue Test Utils

---

## File Structure

### Backend files

- Modify: `backend/tars/database/user_store.py`
  - Add password-hash persistence, password verification helpers, and compatibility migration for existing `users` rows.
- Modify: `backend/tars/main.py`
  - Add login request/response models, `POST /api/auth/login`, and extend `POST /api/users` to require an initial password.
- Create: `backend/tests/test_auth_login_api.py`
  - Cover password hashing, login success/failure, and create-user password requirements.

### Frontend files

- Modify: `frontend/src/api/index.ts`
  - Add `authApi.login()` and typed request/response handling.
- Modify: `frontend/src/types/index.ts`
  - Add auth payload types for login results and optional auth metadata if needed by the store.
- Modify: `frontend/src/stores/auth.ts`
  - Replace API-key-only login assumptions with account login + stored API key session handling.
- Create: `frontend/src/stores/auth.spec.ts`
  - Cover login success/failure, persisted auth bootstrap, and logout cleanup.
- Modify: `frontend/src/router/index.ts`
  - Add `/login`, route meta for shell/no-shell rendering, and auth guards.
- Create: `frontend/src/router/index.spec.ts`
  - Verify redirect rules for anonymous and authenticated users.
- Modify: `frontend/src/App.vue`
  - Render `DesktopShell` only for shell routes and keep startup auth bootstrap.
- Create: `frontend/src/views/LoginView.vue`
  - Page container for the new login experience.
- Create: `frontend/src/components/auth/LoginHeroPanel.vue`
  - Left-side branded product/role explanation.
- Create: `frontend/src/components/auth/LoginCard.vue`
  - Account login form and inline error handling.
- Create: `frontend/src/components/auth/WorkspaceJoinPanel.vue`
  - Expand/collapse join-workspace affordance with invite-code guidance.
- Create: `frontend/src/components/auth/AuthFeedbackAlert.vue`
  - Shared inline feedback surface for auth errors and info.
- Create: `frontend/src/views/LoginView.spec.ts`
  - Cover login page rendering, workspace join expansion, and successful submit behavior.
- Modify: `frontend/src/i18n/index.ts`
  - Add `login.*` and auth error keys in both languages.
- Modify: `frontend/src/components/settings/UserSettings.vue`
  - Require an initial password when admins create a user.
- Modify: `frontend/src/components/settings/UserSettings.spec.ts`
  - Verify the create-user dialog still renders and includes the password field.

### Boundaries

- Do not add a new token/session subsystem; continue using the existing API key as the persisted session credential after successful password login.
- Do not build real workspace membership APIs in this slice; the join-workspace panel is an inline affordance that validates input and feeds the login context.
- Do not restructure the existing desktop shell; only decide whether a route renders inside it.

---

### Task 1: Add Backend Credential Storage

**Files:**
- Modify: `backend/tars/database/user_store.py`
- Test: `backend/tests/test_auth_login_api.py`

- [ ] **Step 1: Write the failing backend storage test**

```python
from tars.database import Database, UserStore
from tars.gateway.permission import UserRole


def test_user_store_hashes_and_verifies_password(tmp_path):
    db = Database(db_path=str(tmp_path / "auth.db"))
    store = UserStore(db)

    user = store.create_user(
        username="alice",
        email="alice@example.com",
        password="S3curePass!",
        role=UserRole.USER,
    )

    assert user.api_key
    assert store.verify_password("alice@example.com", "S3curePass!") is not None
    assert store.verify_password("alice@example.com", "wrong-pass") is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py::test_user_store_hashes_and_verifies_password -q
```

Expected: FAIL because `create_user()` does not accept `password` and `verify_password()` does not exist.

- [ ] **Step 3: Implement password storage and verification**

Update `backend/tars/database/user_store.py` with a backward-compatible schema migration and password helpers:

```python
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class User:
    id: str
    username: str
    email: str
    role: UserRole
    api_key: str
    created_at: datetime
    last_login: Optional[datetime] = None
    password_hash: Optional[str] = None


class UserStore:
    def _init_tables(self):
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT UNIQUE,
                role TEXT NOT NULL,
                api_key TEXT UNIQUE,
                password_hash TEXT,
                created_at TIMESTAMP NOT NULL,
                last_login TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
        if "password_hash" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        conn.commit()

    def _hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return f"{salt.hex()}${digest.hex()}"

    def _check_password(self, password: str, stored: Optional[str]) -> bool:
        if not stored or "$" not in stored:
            return False
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return hmac.compare_digest(actual, expected)

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        password_hash = self._hash_password(password)
        cursor.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, email, role.value, api_key, password_hash, now, None),
        )
        return User(
            id=user_id,
            username=username,
            email=email,
            role=role,
            api_key=api_key,
            password_hash=password_hash,
            created_at=now,
        )

    def verify_password(self, identifier: str, password: str) -> Optional[User]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?",
            (identifier, identifier),
        )
        row = cursor.fetchone()
        if not row:
            return None
        user = User(
            id=row[0],
            username=row[1],
            email=row[2],
            role=UserRole(row[3]),
            api_key=row[4],
            password_hash=row[5],
            created_at=datetime.fromisoformat(row[6]),
            last_login=datetime.fromisoformat(row[7]) if row[7] else None,
        )
        return user if self._check_password(password, user.password_hash) else None
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py::test_user_store_hashes_and_verifies_password -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add backend/tars/database/user_store.py backend/tests/test_auth_login_api.py
git commit -m "feat: add password storage for users"
```

### Task 2: Add Backend Login API And Password-Aware User Creation

**Files:**
- Modify: `backend/tars/main.py`
- Modify: `backend/tars/database/user_store.py`
- Test: `backend/tests/test_auth_login_api.py`

- [ ] **Step 1: Write failing API tests**

Append these tests to `backend/tests/test_auth_login_api.py`:

```python
from fastapi.testclient import TestClient
from tars.main import app, user_store
from tars.gateway.permission import UserRole


def test_login_returns_existing_api_key(tmp_path, monkeypatch):
    test_user = user_store.create_user(
        username="admin",
        email="admin@example.com",
        password="Adm1nPass!",
        role=UserRole.ADMIN,
    )

    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"identifier": "admin@example.com", "password": "Adm1nPass!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["api_key"] == test_user.api_key
    assert data["data"]["user"]["username"] == "admin"


def test_create_user_requires_password(client):
    response = client.post(
        "/api/users",
        json={"username": "bob", "email": "bob@example.com", "role": "user"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py -q
```

Expected: FAIL because `/api/auth/login` does not exist and `POST /api/users` still accepts payloads without `password`.

- [ ] **Step 3: Implement login endpoint and password-aware create user**

Add the request/response models and endpoint in `backend/tars/main.py`:

```python
class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "user"


class AuthLoginRequest(BaseModel):
    identifier: str
    password: str


@app.post("/api/auth/login", response_model=SkillResponse)
async def login(request: AuthLoginRequest):
    user = user_store.verify_password(request.identifier.strip(), request.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user_store.update_last_login(user.id)
    fresh_user = user_store.get_user_by_id(user.id)
    return {
        "success": True,
        "message": "登录成功",
        "data": {
            "api_key": fresh_user.api_key,
            "user": {
                "id": fresh_user.id,
                "username": fresh_user.username,
                "email": fresh_user.email,
                "role": fresh_user.role.value,
                "created_at": fresh_user.created_at.isoformat(),
                "last_login": fresh_user.last_login.isoformat() if fresh_user.last_login else None,
            },
        },
    }


@app.post("/api/users", response_model=SkillResponse)
async def create_user(request: UserCreateRequest):
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="初始密码至少 8 位")
    user = user_store.create_user(request.username, request.email, request.password, role)
    return {
        "success": True,
        "message": "用户创建成功",
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "api_key": user.api_key,
        },
    }
```

- [ ] **Step 4: Run the API tests to verify they pass**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add backend/tars/main.py backend/tars/database/user_store.py backend/tests/test_auth_login_api.py
git commit -m "feat: add account login api"
```

### Task 3: Evolve The Frontend Auth Store And API Client

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/stores/auth.ts`
- Test: `frontend/src/stores/auth.spec.ts`

- [ ] **Step 1: Write the failing store test**

Create `frontend/src/stores/auth.spec.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { authApi } from '@/api'

vi.mock('@/api', () => ({
  authApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}))

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('persists api key after account login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      api_key: 'key-123',
      user: {
        id: 'u1',
        username: 'alice',
        email: 'alice@example.com',
        role: 'user',
        created_at: '2026-05-17T09:00:00Z',
      },
    })

    const store = useAuthStore()
    const ok = await store.loginWithCredentials('alice@example.com', 'S3curePass!')

    expect(ok).toBe(true)
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('apiKey')).toBe('key-123')
  })
})
```

- [ ] **Step 2: Run the store test to verify it fails**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/stores/auth.spec.ts
```

Expected: FAIL because `authApi.login()` and `loginWithCredentials()` do not exist.

- [ ] **Step 3: Implement the minimal auth client and store changes**

Add the types in `frontend/src/types/index.ts`:

```ts
export interface LoginResult {
  api_key: string
  user: User
}
```

Update `frontend/src/api/index.ts`:

```ts
import type { LoginResult } from '@/types'

export const authApi = {
  login: async (identifier: string, password: string): Promise<LoginResult> => {
    const response = await api.post<ApiResponse<LoginResult>>('/auth/login', {
      identifier,
      password,
    })
    return response.data.data as LoginResult
  },
  getCurrentUser: async (apiKey?: string): Promise<User> => {
    const params = apiKey ? { api_key: apiKey } : undefined
    const response = await api.get<User>('/users/me', { params })
    return response.data
  },
}
```

Update `frontend/src/stores/auth.ts`:

```ts
const API_KEY_STORAGE_KEY = 'apiKey'

const loginWithCredentials = async (identifier: string, password: string) => {
  try {
    const response = await authApi.login(identifier, password)
    setApiKey(response.api_key)
    user.value = response.user
    isAuthenticated.value = true
    return true
  } catch {
    logout()
    return false
  }
}

const initAuth = async () => {
  const savedKey = localStorage.getItem(API_KEY_STORAGE_KEY)
  if (!savedKey) return
  try {
    const response = await authApi.getCurrentUser(savedKey)
    apiKey.value = savedKey
    user.value = response
    isAuthenticated.value = true
  } catch {
    logout()
  }
}

return {
  user,
  isAuthenticated,
  apiKey,
  loginWithCredentials,
  login,
  logout,
  initAuth,
}
```

- [ ] **Step 4: Run the store test to verify it passes**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/stores/auth.spec.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add frontend/src/api/index.ts frontend/src/types/index.ts frontend/src/stores/auth.ts frontend/src/stores/auth.spec.ts
git commit -m "feat: add credential login store flow"
```

### Task 4: Add Auth-Aware Routing And Shell Gating

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/router/index.spec.ts`

- [ ] **Step 1: Write the failing routing tests**

Create `frontend/src/router/index.spec.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from './index'
import { useAuthStore } from '@/stores/auth'

describe('router auth guards', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const authStore = useAuthStore()
    authStore.isAuthenticated = false
    await router.push('/login')
  })

  it('redirects anonymous users to /login for shell pages', async () => {
    await router.push('/memory')
    expect(router.currentRoute.value.fullPath).toBe('/login')
  })

  it('redirects authenticated users away from /login', async () => {
    const authStore = useAuthStore()
    authStore.isAuthenticated = true
    await router.push('/login')
    expect(router.currentRoute.value.fullPath).toBe('/')
  })
})
```

- [ ] **Step 2: Run the routing tests to verify they fail**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/router/index.spec.ts
```

Expected: FAIL because `/login` and auth guards do not exist.

- [ ] **Step 3: Implement route meta and shell gating**

Update `frontend/src/router/index.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, shell: false },
    },
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { requiresAuth: true, shell: true, desktopTitleKey: 'desktop.chat.title', desktopSubtitleKey: 'desktop.chat.subtitle' },
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (to.meta.public && authStore.isAuthenticated) return '/'
  if (to.meta.requiresAuth && !authStore.isAuthenticated) return '/login'
  return true
})
```

Update `frontend/src/App.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import DesktopShell from '@/components/layout/DesktopShell.vue'

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

- [ ] **Step 4: Run the routing tests to verify they pass**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/router/index.spec.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add frontend/src/router/index.ts frontend/src/router/index.spec.ts frontend/src/App.vue
git commit -m "feat: gate workspace routes behind auth"
```

### Task 5: Build The Login Page UI

**Files:**
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/components/auth/LoginHeroPanel.vue`
- Create: `frontend/src/components/auth/LoginCard.vue`
- Create: `frontend/src/components/auth/AuthFeedbackAlert.vue`
- Modify: `frontend/src/i18n/index.ts`
- Test: `frontend/src/views/LoginView.spec.ts`

- [ ] **Step 1: Write the failing login page test**

Create `frontend/src/views/LoginView.spec.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from './LoginView.vue'
import { useAuthStore } from '@/stores/auth'

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the brand panel and login card', () => {
    const wrapper = mount(LoginView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('TARS')
    expect(wrapper.text()).toContain('登录并进入')
    expect(wrapper.text()).toContain('加入工作区')
  })
})
```

- [ ] **Step 2: Run the login page test to verify it fails**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/views/LoginView.spec.ts
```

Expected: FAIL because `LoginView.vue` does not exist.

- [ ] **Step 3: Implement the first visible login page**

Create `frontend/src/components/auth/LoginHeroPanel.vue`:

```vue
<template>
  <section class="flex h-full flex-col justify-between rounded-[32px] border border-amber-100/10 bg-[#15110d] p-8 text-stone-100">
    <div>
      <img src="/logo.png" alt="TARS logo" class="h-14 w-14 rounded-2xl" />
      <p class="mt-6 text-sm uppercase tracking-[0.24em] text-amber-300">TARS</p>
      <h1 class="mt-3 text-4xl font-semibold tracking-tight">{{ t('login.heroTitle') }}</h1>
      <p class="mt-4 max-w-xl text-sm leading-7 text-stone-400">{{ t('login.heroDescription') }}</p>
    </div>
    <div class="grid gap-3 md:grid-cols-2">
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-amber-200">{{ t('login.adminTitle') }}</p>
        <p class="mt-2 text-sm text-stone-300">{{ t('login.adminDescription') }}</p>
      </div>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-amber-200">{{ t('login.memberTitle') }}</p>
        <p class="mt-2 text-sm text-stone-300">{{ t('login.memberDescription') }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from '@/i18n'
const { t } = useI18n()
</script>
```

Create `frontend/src/components/auth/AuthFeedbackAlert.vue`:

```vue
<script setup lang="ts">
defineProps<{ message: string; tone?: 'error' | 'info' }>()
</script>

<template>
  <div
    class="rounded-2xl border px-4 py-3 text-sm"
    :class="tone === 'error'
      ? 'border-rose-400/30 bg-rose-500/10 text-rose-100'
      : 'border-amber-300/20 bg-amber-500/10 text-amber-100'"
  >
    {{ message }}
  </div>
</template>
```

Create `frontend/src/components/auth/LoginCard.vue`:

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from '@/i18n'
import AuthFeedbackAlert from './AuthFeedbackAlert.vue'

const emit = defineEmits<{
  submit: [payload: { identifier: string; password: string; workspace: string }]
  toggleJoin: []
}>()

const { t } = useI18n()
const form = reactive({ identifier: '', password: '', workspace: '' })
const errorMessage = ref('')

const onSubmit = () => {
  if (!form.identifier || !form.password) {
    errorMessage.value = t('login.validationRequired')
    return
  }
  errorMessage.value = ''
  emit('submit', { ...form })
}
</script>

<template>
  <section class="rounded-[32px] border border-amber-100/10 bg-[#171310] p-8 shadow-[0_32px_100px_rgba(0,0,0,0.35)]">
    <p class="text-sm uppercase tracking-[0.24em] text-amber-300">{{ t('login.cardEyebrow') }}</p>
    <h2 class="mt-3 text-3xl font-semibold text-stone-50">{{ t('login.cardTitle') }}</h2>
    <p class="mt-2 text-sm text-stone-400">{{ t('login.cardSubtitle') }}</p>
    <div class="mt-6 space-y-4">
      <input v-model="form.identifier" class="w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100" :placeholder="t('login.identifierPlaceholder')" />
      <input v-model="form.password" type="password" class="w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100" :placeholder="t('login.passwordPlaceholder')" />
      <input v-model="form.workspace" class="w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100" :placeholder="t('login.workspacePlaceholder')" />
      <AuthFeedbackAlert v-if="errorMessage" tone="error" :message="errorMessage" />
      <button class="w-full rounded-2xl bg-amber-500 px-4 py-3 font-medium text-stone-950" @click="onSubmit">
        {{ t('login.submit') }}
      </button>
      <div class="grid grid-cols-2 gap-3">
        <button class="rounded-2xl border border-amber-100/10 px-4 py-3 text-sm text-stone-100" @click="$emit('toggleJoin')">
          {{ t('login.joinWorkspace') }}
        </button>
        <button class="rounded-2xl border border-amber-100/10 px-4 py-3 text-sm text-stone-100">
          {{ t('login.forgotPassword') }}
        </button>
      </div>
    </div>
  </section>
</template>
```

Create `frontend/src/views/LoginView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import LoginHeroPanel from '@/components/auth/LoginHeroPanel.vue'
import LoginCard from '@/components/auth/LoginCard.vue'

const joinOpen = ref(false)
const onLoginSubmit = () => {}
</script>

<template>
  <div class="min-h-screen bg-[#0c0b09] px-6 py-8 text-white lg:px-10">
    <div class="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <LoginHeroPanel />
      <LoginCard @submit="onLoginSubmit" @toggleJoin="joinOpen = !joinOpen" />
    </div>
  </div>
</template>
```

Add the first required keys to `frontend/src/i18n/index.ts`:

```ts
'login.heroTitle': '你的团队 AI 工作台',
'login.heroDescription': '一个入口连接聊天、记忆、工具、知识库与会议能力。',
'login.adminTitle': '管理员',
'login.adminDescription': '创建工作区、邀请成员、配置团队资源。',
'login.memberTitle': '成员',
'login.memberDescription': '登录账号、加入工作区、继续协作。',
'login.cardEyebrow': '登录到工作区',
'login.cardTitle': '欢迎回来',
'login.cardSubtitle': '使用账号进入你的 TARS 工作空间',
'login.identifierPlaceholder': '邮箱 / 用户名',
'login.passwordPlaceholder': '密码',
'login.workspacePlaceholder': '工作区名称（可选）/ 邀请码',
'login.submit': '登录并进入',
'login.joinWorkspace': '加入工作区',
'login.forgotPassword': '忘记密码',
'login.validationRequired': '请先填写账号和密码',
```

- [ ] **Step 4: Run the login page test to verify it passes**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/views/LoginView.spec.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add frontend/src/views/LoginView.vue frontend/src/components/auth/LoginHeroPanel.vue frontend/src/components/auth/LoginCard.vue frontend/src/components/auth/AuthFeedbackAlert.vue frontend/src/views/LoginView.spec.ts frontend/src/i18n/index.ts
git commit -m "feat: add login page shell"
```

### Task 6: Wire Login Submission, Join Workspace Panel, And Redirects

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/components/auth/WorkspaceJoinPanel.vue`
- Modify: `frontend/src/components/auth/LoginCard.vue`
- Modify: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/views/LoginView.spec.ts`

- [ ] **Step 1: Write the failing interaction tests**

Extend `frontend/src/views/LoginView.spec.ts`:

```ts
import { vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'

it('expands join workspace panel from the login card', async () => {
  const wrapper = mount(LoginView)
  await wrapper.get('button').trigger('click')
  expect(wrapper.text()).toContain('邀请码')
})

it('calls the auth store and redirects after successful submit', async () => {
  const store = useAuthStore()
  store.loginWithCredentials = vi.fn().mockResolvedValue(true)

  const wrapper = mount(LoginView, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })

  await wrapper.find('input').setValue('alice@example.com')
  await wrapper.find('input[type="password"]').setValue('S3curePass!')
  await wrapper.find('button').trigger('click')

  expect(store.loginWithCredentials).toHaveBeenCalledWith('alice@example.com', 'S3curePass!')
})
```

- [ ] **Step 2: Run the interaction tests to verify they fail**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/views/LoginView.spec.ts
```

Expected: FAIL because the panel and submit wiring are not implemented.

- [ ] **Step 3: Implement login wiring and the join panel**

Create `frontend/src/components/auth/WorkspaceJoinPanel.vue`:

```vue
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from '@/i18n'
import AuthFeedbackAlert from './AuthFeedbackAlert.vue'

const { t } = useI18n()
const form = reactive({ inviteCode: '' })
const errorMessage = ref('')

const applyInvite = () => {
  if (!form.inviteCode.trim()) {
    errorMessage.value = t('login.inviteRequired')
    return
  }
  errorMessage.value = ''
}
</script>

<template>
  <div class="rounded-[28px] border border-amber-100/10 bg-[#14110f] p-5">
    <p class="text-sm font-medium text-stone-100">{{ t('login.joinWorkspace') }}</p>
    <p class="mt-2 text-sm text-stone-400">{{ t('login.joinDescription') }}</p>
    <input v-model="form.inviteCode" class="mt-4 w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100" :placeholder="t('login.invitePlaceholder')" />
    <AuthFeedbackAlert v-if="errorMessage" class="mt-4" tone="error" :message="errorMessage" />
    <div class="mt-4 flex gap-3">
      <button class="rounded-2xl bg-amber-500 px-4 py-3 font-medium text-stone-950" @click="applyInvite">{{ t('login.applyInvite') }}</button>
      <button class="rounded-2xl border border-amber-100/10 px-4 py-3 text-sm text-stone-100">{{ t('login.contactAdmin') }}</button>
    </div>
  </div>
</template>
```

Update `frontend/src/views/LoginView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/i18n'
import LoginHeroPanel from '@/components/auth/LoginHeroPanel.vue'
import LoginCard from '@/components/auth/LoginCard.vue'
import WorkspaceJoinPanel from '@/components/auth/WorkspaceJoinPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const joinOpen = ref(false)
const submitError = ref('')

const onLoginSubmit = async (payload: { identifier: string; password: string; workspace: string }) => {
  const ok = await authStore.loginWithCredentials(payload.identifier, payload.password)
  if (!ok) {
    submitError.value = t('login.invalidCredentials')
    return
  }
  submitError.value = ''
  await router.push(payload.workspace ? `/?workspace=${encodeURIComponent(payload.workspace)}` : '/')
}
</script>

<template>
  <div class="min-h-screen bg-[#0c0b09] px-6 py-8 text-white lg:px-10">
    <div class="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <LoginHeroPanel />
      <div class="space-y-4">
        <LoginCard :error-message="submitError" @submit="onLoginSubmit" @toggleJoin="joinOpen = !joinOpen" />
        <WorkspaceJoinPanel v-if="joinOpen" />
      </div>
    </div>
  </div>
</template>
```

Update the supporting i18n keys:

```ts
'login.invalidCredentials': '用户名或密码错误',
'login.joinDescription': '使用邀请码加入已有工作区，或联系管理员获取邀请。',
'login.invitePlaceholder': '邀请码',
'login.inviteRequired': '请先填写邀请码',
'login.applyInvite': '应用邀请码',
'login.contactAdmin': '联系管理员',
```

- [ ] **Step 4: Run the interaction tests to verify they pass**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/views/LoginView.spec.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add frontend/src/views/LoginView.vue frontend/src/components/auth/WorkspaceJoinPanel.vue frontend/src/components/auth/LoginCard.vue frontend/src/views/LoginView.spec.ts frontend/src/i18n/index.ts
git commit -m "feat: wire login page interactions"
```

### Task 7: Add Initial Password To Admin User Creation

**Files:**
- Modify: `frontend/src/components/settings/UserSettings.vue`
- Modify: `frontend/src/components/settings/UserSettings.spec.ts`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: Write the failing user creation UI test**

Extend `frontend/src/components/settings/UserSettings.spec.ts`:

```ts
it('shows an initial password field in the create user dialog', async () => {
  const wrapper = mount(UserSettings)

  await wrapper.find('button').trigger('click')

  expect(wrapper.html()).toContain('type="password"')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/components/settings/UserSettings.spec.ts
```

Expected: FAIL because the modal has no password field.

- [ ] **Step 3: Implement initial-password support**

Update `frontend/src/api/index.ts`:

```ts
createUser: async (
  username: string,
  email: string,
  password: string,
  role: string = 'user'
): Promise<ApiResponse> => {
  const response = await api.post<ApiResponse>('/users', { username, email, password, role })
  return response.data
}
```

Update `frontend/src/components/settings/UserSettings.vue`:

```ts
const newUser = ref({
  username: '',
  email: '',
  password: '',
  role: 'user',
})

const createUser = async () => {
  if (!newUser.value.username || !newUser.value.email || !newUser.value.password) {
    return
  }
  await authApi.createUser(
    newUser.value.username,
    newUser.value.email,
    newUser.value.password,
    newUser.value.role,
  )
}
```

And add the new field in the template:

```vue
<div>
  <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('login.initialPassword') }}</label>
  <input
    v-model="newUser.password"
    type="password"
    class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
    :placeholder="t('login.initialPasswordPlaceholder')"
  />
</div>
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/frontend && npm run test:unit -- src/components/settings/UserSettings.spec.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add frontend/src/components/settings/UserSettings.vue frontend/src/components/settings/UserSettings.spec.ts frontend/src/api/index.ts frontend/src/i18n/index.ts
git commit -m "feat: require initial password for new users"
```

---

## Self-Review

### Spec coverage

- Brand-first dual-column login page: covered by Task 5.
- Account login with optional workspace context: covered by Tasks 2, 3, and 6.
- Inline join-workspace affordance: covered by Task 6.
- Auth-aware route redirects and no-shell login rendering: covered by Task 4.
- Admin/member practical support for account login rollout: covered by Task 7.

### Placeholder scan

- No `TBD`, `TODO`, or “implement later” placeholders remain.
- Every task names concrete files, commands, and code snippets.

### Type consistency

- Backend login returns `api_key` plus `user`; frontend `LoginResult` uses the same shape.
- Frontend store method name is consistently `loginWithCredentials()`.
- User creation now requires `password` in both backend and frontend API definitions.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-17-login-page.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
