<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import { useI18n } from '@/i18n'

const router = useRouter()
const route = useRoute()
const { locale, toggleLocale, t } = useI18n()

const tabs = [
  { name: 'Personality', path: '/settings' },
  { name: 'Subagents', path: '/settings/subagents' },
  { name: 'Users', path: '/settings/users' }
]
</script>

<template>
  <div class="flex h-screen bg-slate-900">
    <Sidebar />
    <main class="flex-1 flex flex-col">
      <header class="px-6 py-4 border-b border-slate-700">
        <div class="flex items-center justify-between">
          <h1 class="text-xl font-semibold text-white">Settings</h1>
          <div class="flex items-center gap-3">
            <button
              @click="toggleLocale"
              class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
              :title="locale === 'zh' ? 'Switch to English' : '切换到中文'"
            >
              🌐 {{ locale === 'zh' ? 'EN' : '中文' }}
            </button>
            <button 
              @click="router.push('/')"
              class="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors"
            >
              {{ t('back to chat') }}
            </button>
          </div>
        </div>
        
        <nav class="flex gap-1 mt-4">
          <button
            v-for="tab in tabs"
            :key="tab.path"
            @click="router.push(tab.path)"
            class="px-4 py-2 rounded-lg transition-colors"
            :class="route.path === tab.path ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-700'"
          >
            {{ tab.name }}
          </button>
        </nav>
      </header>
      
      <div class="flex-1 p-6 overflow-auto">
        <router-view />
      </div>
    </main>
  </div>
</template>
