<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from '@/i18n'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const tabs = [
  { labelKey: 'admin.tabs.users', path: '/admin/users' },
  { labelKey: 'admin.tabs.roles', path: '/admin/roles' },
  { labelKey: 'admin.tabs.audit', path: '/admin/audit' },
  { labelKey: 'admin.tabs.dashboard', path: '/admin/dashboard' },
  { labelKey: 'admin.tabs.platform', path: '/admin/platform' },
  { labelKey: 'admin.tabs.insightLlm', path: '/admin/insight/llm' },
]
</script>

<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden">
    <header class="border-b border-amber-100/10 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-[11px] uppercase tracking-[0.24em] text-stone-500">{{ t('desktop.admin.eyebrow') }}</div>
          <h1 class="mt-2 text-xl font-semibold text-stone-100">{{ t('admin.title') }}</h1>
        </div>
        <button
          @click="router.push('/')"
          class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition hover:border-amber-300/25 hover:bg-amber-500/10"
        >
          {{ t('common.backToChat') }}
        </button>
      </div>

      <nav class="mt-4 flex gap-2">
        <button
          v-for="tab in tabs"
          :key="tab.path"
          @click="router.push(tab.path)"
          class="rounded-2xl px-4 py-2 transition"
          :class="
            route.path === tab.path
              ? 'bg-amber-500 text-stone-950'
              : 'border border-amber-100/10 bg-white/[0.04] text-stone-400 hover:border-amber-300/25 hover:bg-amber-500/10 hover:text-stone-100'
          "
        >
          {{ t(tab.labelKey) }}
        </button>
      </nav>
    </header>

    <div class="flex-1 overflow-auto p-6">
      <router-view />
    </div>
  </div>
</template>
