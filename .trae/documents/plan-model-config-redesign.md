# Model Config 页面重设计 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将模型配置系统从多 Provider 枚举（Ollama/OpenRouter/Anthropic/OpenAI）简化为两大类（Ollama 本地 + OpenAI 兼容端点），统一管理所有远程 API。

**Architecture:** 后端新增 Endpoint 表替代 CustomModel 表，统一 switch API；前端 ModelsView 改为双区块布局（上 Ollama，下端点卡片），侧边栏按端点分组展示模型。

**Tech Stack:** Python FastAPI + SQLite, Vue 3 + TypeScript + Pinia + TailwindCSS

---

### Task 1: 创建 Endpoint 数据库模型和存储层

**Files:**
- Create: `backend/tars/database/endpoint.py`
- Modify: `backend/tars/database/__init__.py`
- Modify: `backend/tars/database/base.py`

- [ ] **Step 1: 创建 endpoint.py 文件**

```python
# backend/tars/database/endpoint.py
import uuid
import json
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from .base import Database


@dataclass
class Endpoint:
    id: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    models: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EndpointStore:
    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> List[Endpoint]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, api_key, models, enabled, created_at, updated_at
            FROM endpoints
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [self._row_to_endpoint(row) for row in rows]

    def get_enabled(self) -> List[Endpoint]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, api_key, models, enabled, created_at, updated_at
            FROM endpoints
            WHERE enabled = 1
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [self._row_to_endpoint(row) for row in rows]

    def get_by_id(self, endpoint_id: str) -> Optional[Endpoint]:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, api_key, models, enabled, created_at, updated_at
            FROM endpoints WHERE id = ?
        """, (endpoint_id,))
        row = cursor.fetchone()
        return self._row_to_endpoint(row) if row else None

    def create(self, name: str, base_url: str, api_key: Optional[str] = None,
               models: Optional[List[str]] = None) -> Endpoint:
        endpoint_id = str(uuid.uuid4())
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()
        models_json = json.dumps(models or [], ensure_ascii=False)

        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO endpoints (id, name, base_url, api_key, models, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (endpoint_id, name, base_url, api_key, models_json, now, now))
        conn.commit()

        return Endpoint(
            id=endpoint_id, name=name, base_url=base_url,
            api_key=api_key, models=models or [], enabled=True,
            created_at=now, updated_at=now
        )

    def update(self, endpoint_id: str, **kwargs) -> Optional[Endpoint]:
        now = datetime.now(timezone(timedelta(hours=8))).isoformat()
        updates = []
        params = []

        allowed_fields = ["name", "base_url", "api_key", "models", "enabled"]
        for field in allowed_fields:
            if field in kwargs:
                value = kwargs[field]
                if field == "models":
                    value = json.dumps(value, ensure_ascii=False)
                elif field == "enabled":
                    value = 1 if value else 0
                updates.append(f"{field} = ?")
                params.append(value)

        if not updates:
            return self.get_by_id(endpoint_id)

        params.extend([now, endpoint_id])
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE endpoints SET {', '.join(updates)}, updated_at = ?
            WHERE id = ?
        """, params)
        conn.commit()

        return self.get_by_id(endpoint_id)

    def delete(self, endpoint_id: str) -> bool:
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM endpoints WHERE id = ?", (endpoint_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_endpoint(self, row) -> Optional[Endpoint]:
        if not row:
            return None
        models = []
        if row[4]:
            try:
                models = json.loads(row[4])
            except (json.JSONDecodeError, TypeError):
                models = []
        return Endpoint(
            id=row[0], name=row[1], base_url=row[2],
            api_key=row[3], models=models, enabled=bool(row[5]),
            created_at=row[6], updated_at=row[7]
        )
```

- [ ] **Step 2: 在 base.py 的 _init_db 中添加 endpoints 表**

在 `_init_db` 方法的 `CREATE TABLE IF NOT EXISTS cronjobs` 之后添加：

```python
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS endpoints (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT,
                models TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
```

- [ ] **Step 3: 更新 database/__init__.py**

```python
from .endpoint import EndpointStore, Endpoint

__all__ = [
    # ... existing exports ...
    "EndpointStore", "Endpoint",
]
```

---

### Task 2: 重写 models/config.py — 新 API 路由

**Files:**
- Rewrite: `backend/tars/models/config.py`

- [ ] **Step 1: 重写 config.py**

```python
# backend/tars/models/config.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import logging

from tars.models import OllamaProvider, CustomProvider
from tars.database import EndpointStore, Endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["模型配置"])


class EndpointCreate(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None
    models: Optional[List[str]] = None


class EndpointUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    enabled: Optional[bool] = None


class SwitchModelRequest(BaseModel):
    provider: str  # "ollama" | "openai_compatible"
    endpoint_id: Optional[str] = None  # openai_compatible 时必填
    model: str


_endpoint_store: Optional[EndpointStore] = None


def init_endpoint_store(store: EndpointStore):
    global _endpoint_store
    _endpoint_store = store


def get_endpoint_store() -> EndpointStore:
    global _endpoint_store
    if _endpoint_store is None:
        from tars.database import Database, EndpointStore as ES
        db = Database()
        _endpoint_store = ES(db)
    return _endpoint_store


def get_agent():
    from tars.main import agent
    return agent


def _sync_llm_chain(agent):
    agent.dispatcher.set_provider(agent.provider)
    from tars.main import memory_manager
    memory_manager.set_provider(agent.provider)


@router.get("/")
async def get_models():
    """获取可用模型列表和当前选中状态"""
    agent = get_agent()
    store = get_endpoint_store()

    ollama_models = []
    try:
        ollama_provider = OllamaProvider()
        ollama_models = await ollama_provider.list_models()
    except Exception as e:
        logger.warning(f"获取 Ollama 模型列表失败: {e}")

    endpoints = store.get_all()
    current = {
        "provider": "ollama",
        "endpoint_id": None,
        "model": agent.current_model,
    }
    # 尝试从 agent 推断当前 provider
    provider_str = getattr(agent, '_provider_type', 'ollama')
    current["provider"] = provider_str
    if provider_str == "openai_compatible":
        current["endpoint_id"] = getattr(agent, '_endpoint_id', None)

    return {
        "ollama_models": ollama_models,
        "endpoints": [
            {
                "id": e.id,
                "name": e.name,
                "base_url": e.base_url,
                "models": e.models,
                "enabled": e.enabled,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
            }
            for e in endpoints
        ],
        "current": current,
    }


@router.get("/endpoints")
async def list_endpoints():
    store = get_endpoint_store()
    endpoints = store.get_all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "base_url": e.base_url,
            "api_key": e.api_key,
            "models": e.models,
            "enabled": e.enabled,
            "created_at": e.created_at,
            "updated_at": e.updated_at,
        }
        for e in endpoints
    ]


@router.post("/endpoints")
async def create_endpoint(config: EndpointCreate):
    store = get_endpoint_store()
    endpoint = store.create(
        name=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        models=config.models,
    )
    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "base_url": endpoint.base_url,
        "models": endpoint.models,
        "enabled": endpoint.enabled,
        "created_at": endpoint.created_at,
        "updated_at": endpoint.updated_at,
    }


@router.put("/endpoints/{endpoint_id}")
async def update_endpoint(endpoint_id: str, config: EndpointUpdate):
    store = get_endpoint_store()
    existing = store.get_by_id(endpoint_id)
    if not existing:
        raise HTTPException(status_code=404, detail="端点不存在")

    update_data = config.model_dump(exclude_unset=True)
    endpoint = store.update(endpoint_id, **update_data)
    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "base_url": endpoint.base_url,
        "models": endpoint.models,
        "enabled": endpoint.enabled,
        "created_at": endpoint.created_at,
        "updated_at": endpoint.updated_at,
    }


@router.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: str):
    store = get_endpoint_store()
    existing = store.get_by_id(endpoint_id)
    if not existing:
        raise HTTPException(status_code=404, detail="端点不存在")
    success = store.delete(endpoint_id)
    return {"success": success, "message": "删除成功"}


@router.post("/endpoints/{endpoint_id}/fetch-models")
async def fetch_endpoint_models(endpoint_id: str):
    store = get_endpoint_store()
    endpoint = store.get_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")

    try:
        provider = CustomProvider(
            base_url=endpoint.base_url,
            model="",  # 仅用于测试连接
            api_key=endpoint.api_key,
        )
        models = await provider.list_models()
        store.update(endpoint_id, models=models)
        return {"success": True, "models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拉取模型列表失败: {str(e)}")


@router.post("/endpoints/{endpoint_id}/test")
async def test_endpoint(endpoint_id: str):
    store = get_endpoint_store()
    endpoint = store.get_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="端点不存在")

    try:
        provider = CustomProvider(
            base_url=endpoint.base_url,
            model="",
            api_key=endpoint.api_key,
        )
        success, message = await provider.test_connection()
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}


@router.post("/switch")
async def switch_model(request: SwitchModelRequest):
    """统一切换模型接口"""
    agent = get_agent()

    if request.provider == "ollama":
        agent.provider = OllamaProvider(model=request.model)
        agent.current_model = request.model
        agent._provider_type = "ollama"
        agent._endpoint_id = None
        _sync_llm_chain(agent)
        return {
            "success": True,
            "message": f"已切换到本地模型: {request.model}",
            "current_model": request.model,
            "current_provider": "ollama",
        }

    elif request.provider == "openai_compatible":
        if not request.endpoint_id:
            raise HTTPException(status_code=400, detail="openai_compatible 需要指定 endpoint_id")

        store = get_endpoint_store()
        endpoint = store.get_by_id(request.endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=404, detail="端点不存在")
        if not endpoint.enabled:
            raise HTTPException(status_code=400, detail="端点已禁用")

        agent.provider = CustomProvider(
            base_url=endpoint.base_url,
            model=request.model,
            api_key=endpoint.api_key,
        )
        agent.current_model = request.model
        agent._provider_type = "openai_compatible"
        agent._endpoint_id = request.endpoint_id
        _sync_llm_chain(agent)
        return {
            "success": True,
            "message": f"已切换到 {endpoint.name}: {request.model}",
            "current_model": request.model,
            "current_provider": "openai_compatible",
            "endpoint_id": request.endpoint_id,
        }

    else:
        raise HTTPException(status_code=400, detail=f"不支持的 provider 类型: {request.provider}")
```

- [ ] **Step 2: 更新 main.py 中的初始化**

在 `main.py` 中找到 `init_custom_model_store` 相关代码，替换为：

```python
from tars.database import EndpointStore
from tars.models.config import init_endpoint_store

endpoint_store = EndpointStore(db)
init_endpoint_store(endpoint_store)
```

同时移除 `from tars.database import CustomModelStore` 和 `init_custom_model_store` 相关代码。

---

### Task 3: 简化 agent/agent.py

**Files:**
- Modify: `backend/tars/agent/agent.py`

- [ ] **Step 1: 简化 switch 逻辑**

```python
    def switch_model(self, model_name: str) -> bool:
        try:
            self.provider = OllamaProvider(model=model_name)
            self.current_model = model_name
            self.dispatcher.set_provider(self.provider)
            return True
        except Exception:
            return False

    def switch_to_custom_model(self, model_id: str, base_url: str, model: str, api_key: str = None) -> bool:
        try:
            self.provider = CustomProvider(base_url=base_url, model=model, api_key=api_key)
            self.current_model = model
            self.dispatcher.set_provider(self.provider)
            return True
        except Exception:
            return False
```

替换为：

```python
    def switch_model(self, model_name: str) -> bool:
        try:
            self.provider = OllamaProvider(model=model_name)
            self.current_model = model_name
            self._provider_type = "ollama"
            self._endpoint_id = None
            self.dispatcher.set_provider(self.provider)
            return True
        except Exception:
            return False
```

同时移除 `switch_to_custom_model` 方法。

- [ ] **Step 2: 在 `__init__` 中添加 `_provider_type` 和 `_endpoint_id` 属性**

在 `self.current_model` 初始化之后添加：

```python
        self._provider_type: str = "ollama"
        self._endpoint_id: Optional[str] = None
```

---

### Task 4: 删除 OpenRouterProvider

**Files:**
- Delete: `backend/tars/models/openrouter.py`
- Modify: `backend/tars/models/__init__.py`

- [ ] **Step 1: 更新 models/__init__.py**

```python
from .base import LLMProvider, ChatMessage, ModelResponse
from .ollama import OllamaProvider
from .custom import CustomProvider

__all__ = ["LLMProvider", "ChatMessage", "ModelResponse", "OllamaProvider", "CustomProvider"]
```

- [ ] **Step 2: 删除 openrouter.py 文件**

---

### Task 5: 更新前端类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 添加 Endpoint 类型**

在 `ChatHistoryMessage` 接口之后添加：

```typescript
export interface Endpoint {
  id: string
  name: string
  base_url: string
  api_key?: string
  models: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ModelListResponse {
  ollama_models: string[]
  endpoints: Endpoint[]
  current: {
    provider: string
    endpoint_id: string | null
    model: string
  }
}
```

---

### Task 6: 更新前端 API 层

**Files:**
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: 更新 modelApi**

```typescript
export const modelApi = {
  getModels: async (): Promise<ModelListResponse> => {
    const response = await api.get<ModelListResponse>('/models/')
    return response.data
  },

  switchModel: async (provider: string, model: string, endpointId?: string): Promise<any> => {
    const response = await api.post<any>('/models/switch', {
      provider,
      endpoint_id: endpointId,
      model,
    })
    return response.data
  },

  // Endpoint CRUD
  listEndpoints: async (): Promise<Endpoint[]> => {
    const response = await api.get<Endpoint[]>('/models/endpoints')
    return response.data
  },

  createEndpoint: async (data: { name: string; base_url: string; api_key?: string; models?: string[] }): Promise<Endpoint> => {
    const response = await api.post<Endpoint>('/models/endpoints', data)
    return response.data
  },

  updateEndpoint: async (id: string, data: Partial<Endpoint>): Promise<Endpoint> => {
    const response = await api.put<Endpoint>(`/models/endpoints/${id}`, data)
    return response.data
  },

  deleteEndpoint: async (id: string): Promise<void> => {
    await api.delete(`/models/endpoints/${id}`)
  },

  fetchEndpointModels: async (id: string): Promise<{ success: boolean; models: string[] }> => {
    const response = await api.post(`/models/endpoints/${id}/fetch-models`)
    return response.data
  },

  testEndpoint: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.post(`/models/endpoints/${id}/test`)
    return response.data
  },
}
```

---

### Task 7: 重构前端 settings store

**Files:**
- Modify: `frontend/src/stores/settings.ts`

- [ ] **Step 1: 重写 store**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { personalityApi, subagentApi, modelApi } from '@/api'
import type { Personality, SubAgent, Endpoint } from '@/types'

const STORAGE_KEY = 'tars_settings'

interface StoredSettings {
  provider?: string
  endpoint_id?: string
  model?: string
}

export const useSettingsStore = defineStore('settings', () => {
  const personality = ref<Personality | null>(null)
  const subagents = ref<Record<string, SubAgent>>({})
  const ollamaModels = ref<string[]>([])
  const endpoints = ref<Endpoint[]>([])
  const currentProvider = ref('ollama')
  const currentEndpointId = ref<string | null>(null)
  const currentModel = ref('')
  const loading = ref(false)

  const _loadFromStorage = (): StoredSettings => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) return JSON.parse(stored)
    } catch {}
    return {}
  }

  const _saveToStorage = () => {
    try {
      const settings: StoredSettings = {
        provider: currentProvider.value,
        endpoint_id: currentEndpointId.value || undefined,
        model: currentModel.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch {}
  }

  const loadPersonality = async () => {
    loading.value = true
    try {
      const response = await personalityApi.getPersonality()
      if (response.success && response.data) {
        personality.value = response.data
      }
    } catch {
      personality.value = null
    } finally {
      loading.value = false
    }
  }

  const updatePersonality = async (data: {
    parameters?: Partial<Personality['parameters']>
    communication_style?: string
    behavior_rules?: string[]
  }) => {
    loading.value = true
    try {
      const response = await personalityApi.updatePersonality(data)
      if (response.success && response.data) {
        personality.value = response.data
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  const loadSubagents = async () => {
    loading.value = true
    try {
      const response = await subagentApi.getSubagents()
      subagents.value = response.subagents
    } catch {
      subagents.value = {}
    } finally {
      loading.value = false
    }
  }

  const updateSubagent = async (agentType: string, config: Partial<SubAgent>) => {
    loading.value = true
    try {
      const response = await subagentApi.updateSubagent(agentType, config)
      if (response.success) {
        await loadSubagents()
        return true
      }
      return false
    } finally {
      loading.value = false
    }
  }

  const loadModels = async () => {
    loading.value = true
    try {
      const response = await modelApi.getModels()
      ollamaModels.value = response.ollama_models
      endpoints.value = response.endpoints

      const stored = _loadFromStorage()
      currentProvider.value = response.current.provider || stored.provider || 'ollama'
      currentEndpointId.value = response.current.endpoint_id || stored.endpoint_id || null
      currentModel.value = response.current.model || stored.model || ''

      // 从 localStorage 恢复选中状态
      if (stored.model && stored.model !== response.current.model) {
        const result = await modelApi.switchModel(
          stored.provider || 'ollama',
          stored.model,
          stored.endpoint_id,
        )
        if (result.success) {
          currentModel.value = stored.model
          currentProvider.value = stored.provider || 'ollama'
          currentEndpointId.value = stored.endpoint_id || null
        }
      }
    } catch {
      ollamaModels.value = []
      endpoints.value = []
      currentModel.value = ''
      currentProvider.value = 'ollama'
      currentEndpointId.value = null
    } finally {
      loading.value = false
    }
  }

  const switchModel = async (provider: string, model: string, endpointId?: string) => {
    loading.value = true
    try {
      const response = await modelApi.switchModel(provider, model, endpointId)
      if (response.success) {
        currentModel.value = model
        currentProvider.value = provider
        currentEndpointId.value = endpointId || null
        _saveToStorage()
        return true
      }
      return false
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  const initSettings = async () => {
    await Promise.all([
      loadPersonality(),
      loadSubagents(),
      loadModels(),
    ])
  }

  return {
    personality,
    subagents,
    ollamaModels,
    endpoints,
    currentProvider,
    currentEndpointId,
    currentModel,
    loading,
    loadPersonality,
    updatePersonality,
    loadSubagents,
    updateSubagent,
    loadModels,
    switchModel,
    initSettings,
  }
})
```

---

### Task 8: 重写 ModelsView.vue — 双区块布局

**Files:**
- Rewrite: `frontend/src/views/ModelsView.vue`

- [ ] **Step 1: 重写 ModelsView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/i18n'
import { modelApi } from '@/api'
import type { Endpoint } from '@/types'

const router = useRouter()
const settingsStore = useSettingsStore()
const toast = useToast()
const { locale, toggleLocale, t } = useI18n()

const ollamaStatus = ref<'loading' | 'connected' | 'disconnected'>('loading')
const showAddEndpoint = ref(false)
const editingEndpoint = ref<Endpoint | null>(null)
const addForm = ref({ name: '', base_url: '', api_key: '' })
const testingId = ref<string | null>(null)
const fetchingId = ref<string | null>(null)
const switching = ref(false)

const ollamaBaseUrl = 'http://localhost:11434'

onMounted(async () => {
  await settingsStore.loadModels()
  checkOllamaStatus()
})

const checkOllamaStatus = async () => {
  ollamaStatus.value = 'loading'
  try {
    const res = await fetch('http://localhost:11434/api/tags')
    if (res.ok) {
      ollamaStatus.value = 'connected'
    } else {
      ollamaStatus.value = 'disconnected'
    }
  } catch {
    ollamaStatus.value = 'disconnected'
  }
}

const switchToOllama = async (model: string) => {
  if (switching.value) return
  switching.value = true
  try {
    const success = await settingsStore.switchModel('ollama', model)
    if (success) {
      toast.success(`${t('sidebar.switchedTo')}: ${model}`)
    } else {
      toast.error(t('sidebar.switchFailed'))
    }
  } finally {
    switching.value = false
  }
}

const switchToEndpoint = async (endpointId: string, model: string) => {
  if (switching.value) return
  switching.value = true
  try {
    const success = await settingsStore.switchModel('openai_compatible', model, endpointId)
    if (success) {
      toast.success(`${t('sidebar.switchedTo')}: ${model}`)
    } else {
      toast.error(t('sidebar.switchFailed'))
    }
  } finally {
    switching.value = false
  }
}

const addEndpoint = async () => {
  if (!addForm.value.name || !addForm.value.base_url) return
  try {
    await modelApi.createEndpoint(addForm.value)
    await settingsStore.loadModels()
    showAddEndpoint.value = false
    addForm.value = { name: '', base_url: '', api_key: '' }
    toast.success(t('common.success'))
  } catch {
    toast.error(t('common.error'))
  }
}

const deleteEndpoint = async (id: string) => {
  if (!confirm(t('toolDetail.uninstallConfirm'))) return
  try {
    await modelApi.deleteEndpoint(id)
    await settingsStore.loadModels()
    toast.success(t('common.success'))
  } catch {
    toast.error(t('common.error'))
  }
}

const testEndpoint = async (id: string) => {
  testingId.value = id
  try {
    const result = await modelApi.testEndpoint(id)
    if (result.success) {
      toast.success(result.message)
    } else {
      toast.error(result.message)
    }
  } catch {
    toast.error(t('common.error'))
  } finally {
    testingId.value = null
  }
}

const fetchModels = async (id: string) => {
  fetchingId.value = id
  try {
    const result = await modelApi.fetchEndpointModels(id)
    if (result.success) {
      await settingsStore.loadModels()
      toast.success(`${t('common.success')}: ${result.models.length} models`)
    }
  } catch {
    toast.error(t('common.error'))
  } finally {
    fetchingId.value = null
  }
}

const isCurrentOllama = (model: string) => {
  return settingsStore.currentProvider === 'ollama' && settingsStore.currentModel === model
}

const isCurrentEndpointModel = (endpointId: string, model: string) => {
  return settingsStore.currentProvider === 'openai_compatible'
    && settingsStore.currentEndpointId === endpointId
    && settingsStore.currentModel === model
}
</script>

<template>
  <div class="flex h-screen bg-slate-900">
    <Sidebar />

    <main class="flex-1 flex flex-col">
      <header class="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span class="text-white font-bold text-lg">T</span>
          </div>
          <div>
            <h1 class="text-lg font-semibold text-white">{{ t('models.title') }}</h1>
            <p class="text-sm text-slate-400">{{ t('models.subtitle') }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <button @click="toggleLocale" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors">
            🌐 {{ locale === 'zh' ? 'EN' : '中文' }}
          </button>
          <button @click="router.push('/')" class="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
            <span>{{ t('models.backToChat') }}</span>
          </button>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto">
        <div class="max-w-4xl mx-auto p-8 space-y-8">

          <!-- Block 1: Ollama Local Models -->
          <section class="bg-slate-800 rounded-xl p-6">
            <div class="flex items-center justify-between mb-6">
              <div>
                <h2 class="text-lg font-medium text-white">Ollama {{ t('models.ollama') }}</h2>
                <div class="flex items-center gap-2 mt-1">
                  <span class="w-2 h-2 rounded-full"
                    :class="ollamaStatus === 'connected' ? 'bg-green-400' : ollamaStatus === 'loading' ? 'bg-yellow-400' : 'bg-red-400'">
                  </span>
                  <span class="text-sm text-slate-400">
                    {{ ollamaStatus === 'connected' ? t('common.enabled') : ollamaStatus === 'loading' ? t('common.loading') : t('common.disabled') }}
                  </span>
                  <span class="text-xs text-slate-500 ml-2">{{ ollamaBaseUrl }}</span>
                </div>
              </div>
              <button @click="checkOllamaStatus" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm text-white transition-colors">
                {{ t('common.test') }}
              </button>
            </div>

            <div v-if="settingsStore.ollamaModels.length === 0" class="text-center py-8">
              <p class="text-slate-400 mb-2">{{ t('common.loading') }}</p>
              <p class="text-sm text-slate-500">ollama pull &lt;model&gt;</p>
            </div>

            <div v-else class="flex flex-wrap gap-3">
              <button v-for="model in settingsStore.ollamaModels" :key="model"
                @click="switchToOllama(model)" :disabled="switching"
                class="px-4 py-2 rounded-lg border-2 text-sm font-medium transition-all"
                :class="isCurrentOllama(model)
                  ? 'border-green-500 bg-slate-700 text-white'
                  : 'border-slate-600 bg-slate-700/50 text-slate-300 hover:border-slate-500 hover:text-white'">
                <span class="flex items-center gap-2">
                  {{ model }}
                  <span v-if="isCurrentOllama(model)" class="text-green-400">✓</span>
                </span>
              </button>
            </div>
          </section>

          <!-- Block 2: OpenAI Compatible Endpoints -->
          <section class="bg-slate-800 rounded-xl p-6">
            <div class="flex items-center justify-between mb-6">
              <h2 class="text-lg font-medium text-white">OpenAI {{ t('models.openai') }}</h2>
              <button @click="showAddEndpoint = !showAddEndpoint"
                class="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white text-sm transition-colors">
                {{ showAddEndpoint ? t('common.cancel') : '+ ' + t('common.create') }}
              </button>
            </div>

            <!-- Add Endpoint Form -->
            <div v-if="showAddEndpoint" class="bg-slate-700 rounded-lg p-4 mb-6 space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-1">{{ t('addSkill.name') }} *</label>
                  <input v-model="addForm.name" type="text" placeholder="DeepSeek API"
                    class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-1">Base URL *</label>
                  <input v-model="addForm.base_url" type="text" placeholder="https://api.deepseek.com/v1"
                    class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-1">API Key</label>
                <input v-model="addForm.api_key" type="password" placeholder="sk-..."
                  class="w-full bg-slate-600 border border-slate-500 rounded-lg px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <button @click="addEndpoint" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors">
                {{ t('common.save') }}
              </button>
            </div>

            <!-- Endpoint Cards -->
            <div v-if="settingsStore.endpoints.length === 0 && !showAddEndpoint" class="text-center py-6 text-slate-400">
              {{ t('common.loading') }}
            </div>

            <div v-else class="space-y-4">
              <div v-for="ep in settingsStore.endpoints" :key="ep.id"
                class="bg-slate-700 rounded-lg p-4">
                <div class="flex items-center justify-between mb-3">
                  <div>
                    <h3 class="text-white font-medium">{{ ep.name }}</h3>
                    <p class="text-xs text-slate-400 mt-0.5">{{ ep.base_url }}</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <button @click="testEndpoint(ep.id)" :disabled="testingId === ep.id"
                      class="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded text-white text-xs transition-colors">
                      {{ testingId === ep.id ? '...' : t('common.test') }}
                    </button>
                    <button @click="fetchModels(ep.id)" :disabled="fetchingId === ep.id"
                      class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-white text-xs transition-colors">
                      {{ fetchingId === ep.id ? '...' : t('common.search') }}
                    </button>
                    <button @click="deleteEndpoint(ep.id)"
                      class="px-3 py-1.5 bg-red-600/30 hover:bg-red-600/50 rounded text-red-400 text-xs transition-colors">
                      {{ t('common.delete') }}
                    </button>
                  </div>
                </div>

                <!-- Model chips -->
                <div v-if="ep.models.length > 0" class="flex flex-wrap gap-2">
                  <button v-for="m in ep.models" :key="m"
                    @click="switchToEndpoint(ep.id, m)" :disabled="switching"
                    class="px-3 py-1.5 rounded-lg border text-xs font-medium transition-all"
                    :class="isCurrentEndpointModel(ep.id, m)
                      ? 'border-green-500 bg-slate-600 text-white'
                      : 'border-slate-600 text-slate-400 hover:border-slate-500 hover:text-white'">
                    <span class="flex items-center gap-1">
                      {{ m }}
                      <span v-if="isCurrentEndpointModel(ep.id, m)" class="text-green-400">✓</span>
                    </span>
                  </button>
                </div>
                <p v-else class="text-xs text-slate-500">{{ t('common.loading') }}</p>
              </div>
            </div>
          </section>

        </div>
      </div>
    </main>
  </div>
</template>
```

---

### Task 9: 重写 Sidebar.vue — 无 tab 分组

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.vue`

- [ ] **Step 1: 重写模型 popover 部分**

移除 `activeTab` 相关逻辑，改为按端点分组展示：

```vue
<script setup lang="ts">
// ... existing imports ...
// 移除: type TabType = 'ollama' | 'custom' | 'openrouter'
// 移除: const activeTab = ref<TabType>('ollama')
// 移除: const tabs = [...]

// 修改 switchModel:
const switchModel = async (modelName: string) => {
  if (switching.value) return
  switching.value = true
  try {
    const success = await settingsStore.switchModel('ollama', modelName)
    if (success) {
      toast.success(`${t('sidebar.switchedTo')}: ${modelName}`)
    } else {
      toast.error(t('sidebar.switchFailed'))
    }
  } catch (e) {
    toast.error(t('sidebar.switchFailed'))
  } finally {
    switching.value = false
  }
}

const switchEndpointModel = async (endpointId: string, modelName: string) => {
  if (switching.value) return
  switching.value = true
  try {
    const success = await settingsStore.switchModel('openai_compatible', modelName, endpointId)
    if (success) {
      toast.success(`${t('sidebar.switchedTo')}: ${modelName}`)
    } else {
      toast.error(t('sidebar.switchFailed'))
    }
  } catch (e) {
    toast.error(t('sidebar.switchFailed'))
  } finally {
    switching.value = false
  }
}

// 修改 isCurrentModel:
const isCurrentModel = (modelName: string) => {
  return settingsStore.currentProvider === 'ollama' && settingsStore.currentModel === modelName
}

const isCurrentEndpointModel = (endpointId: string, modelName: string) => {
  return settingsStore.currentProvider === 'openai_compatible'
    && settingsStore.currentEndpointId === endpointId
    && settingsStore.currentModel === modelName
}
</script>
```

Popover 模板替换为：

```vue
<!-- 模型选择 Popover（无 tab 分组） -->
<div v-if="!collapsed" class="border-t border-slate-700 p-3 relative">
  <button @click="showModelPopover = !showModelPopover"
    class="w-full flex items-center justify-between px-3 py-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors">
    <div class="flex items-center gap-2 min-w-0">
      <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
        :class="settingsStore.currentProvider === 'openai_compatible' ? 'bg-green-400' : 'bg-blue-400'"></span>
      <span class="text-xs text-slate-300 truncate">{{ settingsStore.currentModel || t('common.loading') }}</span>
    </div>
    <svg class="w-4 h-4 text-slate-500 flex-shrink-0 transition-transform" :class="showModelPopover ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
    </svg>
  </button>

  <!-- Popover -->
  <div v-if="showModelPopover" class="absolute bottom-full left-3 right-3 mb-1 bg-slate-800 border border-slate-600 rounded-xl shadow-2xl z-50 overflow-hidden">
    <div class="max-h-60 overflow-y-auto">
      <!-- Ollama 本地模型 -->
      <div v-if="settingsStore.ollamaModels.length > 0">
        <div class="px-3 py-1.5 text-xs text-slate-500 font-medium bg-slate-800/50">{{ t('sidebar.ollama') }}</div>
        <button v-for="model in settingsStore.ollamaModels" :key="model"
          @click="switchModel(model); showModelPopover = false" :disabled="switching"
          class="w-full px-3 py-2 text-sm text-left flex items-center justify-between transition-colors"
          :class="isCurrentModel(model) ? 'bg-slate-600 border-l-4 border-green-500 text-white' : 'hover:bg-slate-600/50 text-slate-300 border-l-4 border-transparent'">
          <span class="truncate">{{ model }}</span>
          <span v-if="isCurrentModel(model)" class="text-green-400 text-xs">✓</span>
        </button>
      </div>

      <!-- 端点分组 -->
      <template v-for="ep in settingsStore.endpoints" :key="ep.id">
        <div v-if="ep.models.length > 0" class="border-t border-slate-700">
          <div class="px-3 py-1.5 text-xs text-slate-500 font-medium bg-slate-800/50">{{ ep.name }}</div>
          <button v-for="m in ep.models" :key="`${ep.id}-${m}`"
            @click="switchEndpointModel(ep.id, m); showModelPopover = false" :disabled="switching"
            class="w-full px-3 py-2 text-sm text-left flex items-center justify-between transition-colors"
            :class="isCurrentEndpointModel(ep.id, m) ? 'bg-slate-600 border-l-4 border-green-500 text-white' : 'hover:bg-slate-600/50 text-slate-300 border-l-4 border-transparent'">
            <span class="truncate">{{ m }}</span>
            <span v-if="isCurrentEndpointModel(ep.id, m)" class="text-green-400 text-xs">✓</span>
          </button>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-if="settingsStore.ollamaModels.length === 0 && settingsStore.endpoints.length === 0" class="px-3 py-4 text-center text-slate-400 text-sm">
        {{ t('common.loading') }}
      </div>
    </div>

    <!-- 底部跳转 -->
    <div class="border-t border-slate-700">
      <button @click="router.push('/models'); showModelPopover = false"
        class="w-full px-3 py-2 text-sm text-blue-400 hover:bg-slate-600/50 text-left transition-colors">
        ⚙ {{ t('models.title') }}
      </button>
    </div>
  </div>
</div>
```

---

### Task 10: 删除 ModelSettings.vue

**Files:**
- Delete: `frontend/src/components/settings/ModelSettings.vue`

- [ ] **Step 1: 删除 ModelSettings.vue 文件**

---

### Task 11: 更新 i18n 翻译

**Files:**
- Modify: `frontend/src/i18n/index.ts`

- [ ] **Step 1: 更新 models 相关翻译**

```typescript
    // Models
    'models.title': '模型配置',
    'models.subtitle': '管理 AI 模型',
    'models.backToChat': '返回聊天',
    'models.ollama': '本地模型',
    'models.ollamaDesc': '本地运行的大模型，隐私性好，速度快',
    'models.openai': '兼容端点',
    'models.openaiDesc': 'OpenAI 兼容 API',
```

英文部分：

```typescript
    // Models
    'models.title': 'Model Config',
    'models.subtitle': 'Manage AI Models',
    'models.backToChat': 'Back to Chat',
    'models.ollama': 'Local Models',
    'models.ollamaDesc': 'Local LLMs with privacy and fast response',
    'models.openai': 'Compatible Endpoints',
    'models.openaiDesc': 'OpenAI Compatible API',
```

---

### Task 12: 更新 main.py — 移除旧引用

**Files:**
- Modify: `backend/tars/main.py`

- [ ] **Step 1: 移除 CustomModelStore 相关代码**

找到 `from tars.database import CustomModelStore` 和 `init_custom_model_store` 相关代码，替换为 `EndpointStore` 和 `init_endpoint_store`。

- [ ] **Step 2: 移除 OpenRouterProvider 导入**

找到 `from tars.models import ... OpenRouterProvider` 移除 OpenRouterProvider 引用。