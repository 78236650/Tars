# TARS UI 改进计划

## 问题汇总

| # | 问题 | 当前状态 | 期望状态 |
|---|------|----------|----------|
| 1 | Sidebar 缩进功能 | 显示完整菜单 | 点击按钮折叠/展开 |
| 2 | 跳转路径错误 | 跳转到 /settings | 跳转到 /models |
| 3 | 双语切换 | 无国际化 | 中文/英文切换 |
| 4 | Tools/Skills 无法使用 | 工具未执行 | Agent 能调用工具 |
| 5 | 页面状态不保持 | 刷新丢失状态 | 保持状态 |

---

## 实施方案

### 1. Sidebar 缩进功能

**文件**: `frontend/src/components/layout/Sidebar.vue`

**实现**:
- 添加 `collapsed` 状态（ref）
- 添加折叠按钮
- 折叠时只显示图标，展开时显示完整菜单
- 模型区域在折叠时只显示当前模型

### 2. 修复跳转路径

**文件**: `frontend/src/components/layout/Sidebar.vue`

**改动**: 第 195 行
```diff
- @click="router.push('/settings')"
+ @click="router.push('/models')"
```

### 3. 双语切换

**新增文件**: `frontend/src/i18n/index.ts`
**修改文件**: 所有 View 组件

**实现**:
- 简单的翻译对象存储在 localStorage
- Settings 页面添加语言切换按钮

### 4. Tools/Skills 功能

**问题分析**:
- WeatherTool 已注册但需要 OpenWeatherMap API Key
- 没有 API Key 时返回模拟数据
- Agent 的 tool_calling.py 已配置 weather 关键词

**解决方案**:
1. 检查 OpenWeatherMap API Key 配置
2. 增强 WeatherTool 的模拟模式（更好的模拟数据）
3. 验证 Agent 工具调用流程

**文件**:
- `backend/tars/execution/weather.py`
- `backend/tars/agent/tool_calling.py`

### 5. 页面状态保持

**文件**: `frontend/src/stores/useAppStore.ts`

**实现**:
- 使用 localStorage 持久化状态
- 页面加载时恢复状态

---

## 具体改动

### Sidebar.vue 改动

```vue
<script setup lang="ts">
// 添加折叠状态
const collapsed = ref(false)
const toggleCollapse = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem('sidebar_collapsed', String(collapsed.value))
}

// 恢复状态
onMounted(() => {
  const saved = localStorage.getItem('sidebar_collapsed')
  if (saved === 'true') collapsed.value = true
  settingsStore.loadModels()
})
</script>

<template>
  <!-- 折叠按钮 -->
  <button @click="toggleCollapse" class="...">
    {{ collapsed ? '→' : '←' }}
  </button>

  <!-- 折叠/展开内容 -->
  <div v-if="collapsed" class="w-16">
    <!-- 只显示图标 -->
  </div>
  <div v-else class="w-64">
    <!-- 完整菜单 -->
  </div>
</template>
```

### i18n 实现

```typescript
// frontend/src/i18n/index.ts
export const messages = {
  zh: {
    chat: '聊天', models: '模型', tools: '工具', settings: '设置',
    'current model': '当前模型', 'add custom model': '添加自定义模型'
  },
  en: {
    chat: 'Chat', models: 'Models', tools: 'Tools', settings: 'Settings',
    'current model': 'Current Model', 'add custom model': 'Add Custom Model'
  }
}
```

---

## 实施顺序

1. **问题 2**: 修复跳转路径（1 分钟）
2. **问题 1**: Sidebar 缩进功能（15 分钟）
3. **问题 5**: 页面状态保持（10 分钟）
4. **问题 3**: 双语切换（15 分钟）
5. **问题 4**: Tools/Skills 调试（20 分钟）

---

## 验证步骤

1. 修复后测试跳转路径
2. 测试 Sidebar 折叠/展开
3. 测试状态持久化
4. 测试语言切换
5. 测试 Agent 调用工具
