<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

interface LlmModel {
  provider: string
  model: string
  calls: number
  tokens_in: number
  tokens_out: number
}

interface Alert {
  type: string
  severity: string
  title: string
  description: string
}

interface DashboardData {
  llm: {
    total_tokens_7d: number
    by_model: LlmModel[]
  }
  memory: {
    total: number
    corrections: number
    solutions: number
  }
  alerts: Alert[]
  entities: number
}

const data = ref<DashboardData | null>(null)
const loading = ref(true)
const error = ref('')

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function severityClass(s: string): string {
  return s === 'warning' ? 'text-amber-400' : s === 'critical' ? 'text-red-400' : 'text-stone-400'
}

onMounted(async () => {
  try {
    const r = await api.get('/admin/dashboard')
    data.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="py-12 text-center text-stone-400">加载中...</div>
  <div v-else-if="error" class="py-12 text-center text-red-400">{{ error }}</div>
  <div v-else-if="data" class="space-y-6">
    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
        <div class="text-xs text-stone-500">7d Token 消耗</div>
        <div class="mt-1 text-2xl font-semibold text-stone-100">{{ fmtTokens(data.llm.total_tokens_7d) }}</div>
      </div>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
        <div class="text-xs text-stone-500">记忆总数</div>
        <div class="mt-1 text-2xl font-semibold text-stone-100">{{ data.memory.total }}</div>
      </div>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
        <div class="text-xs text-stone-500">解决思路</div>
        <div class="mt-1 text-2xl font-semibold text-amber-400">{{ data.memory.solutions }}</div>
      </div>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
        <div class="text-xs text-stone-500">实体数</div>
        <div class="mt-1 text-2xl font-semibold text-stone-100">{{ data.entities }}</div>
      </div>
    </div>

    <!-- LLM 用量表 -->
    <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
      <h3 class="mb-3 text-sm font-semibold text-stone-200">LLM 用量（7天）</h3>
      <div v-if="data.llm.by_model.length === 0" class="text-sm text-stone-500">暂无数据</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left text-stone-500">
            <th class="pb-2">模型</th>
            <th class="pb-2">提供商</th>
            <th class="pb-2 text-right">调用</th>
            <th class="pb-2 text-right">输入 Token</th>
            <th class="pb-2 text-right">输出 Token</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in data.llm.by_model" :key="m.provider + m.model" class="border-t border-amber-100/5">
            <td class="py-2 text-stone-200">{{ m.model }}</td>
            <td class="py-2 text-stone-400">{{ m.provider }}</td>
            <td class="py-2 text-right text-stone-300">{{ m.calls }}</td>
            <td class="py-2 text-right text-stone-300">{{ fmtTokens(m.tokens_in) }}</td>
            <td class="py-2 text-right text-stone-300">{{ fmtTokens(m.tokens_out) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 预警列表 -->
    <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
      <h3 class="mb-3 text-sm font-semibold text-stone-200">
        预警
        <span v-if="data.alerts.length" class="ml-2 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">{{ data.alerts.length }}</span>
      </h3>
      <div v-if="data.alerts.length === 0" class="text-sm text-stone-500">✅ 暂无预警</div>
      <div v-for="a in data.alerts" :key="a.title" class="mb-2 rounded-xl border border-amber-100/5 bg-white/[0.02] p-3">
        <div class="flex items-center gap-2">
          <span :class="severityClass(a.severity)" class="text-xs font-semibold uppercase">{{ a.severity }}</span>
          <span class="text-sm font-medium text-stone-200">{{ a.title }}</span>
        </div>
        <div class="mt-1 text-xs text-stone-400">{{ a.description }}</div>
      </div>
    </div>

    <!-- 纠正统计 -->
    <div class="rounded-2xl border border-amber-100/10 bg-white/[0.04] p-4">
      <h3 class="mb-3 text-sm font-semibold text-stone-200">纠正统计</h3>
      <div class="flex items-center gap-4">
        <div class="text-sm text-stone-400">
          用户纠正次数：<span class="font-semibold text-stone-200">{{ data.memory.corrections }}</span>
        </div>
        <div v-if="data.memory.corrections >= 3" class="text-xs text-amber-400">
          ⚠️ 纠正次数较多，建议检查 Evolution 优化效果
        </div>
      </div>
    </div>
  </div>
</template>
