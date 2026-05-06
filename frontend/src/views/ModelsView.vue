<script setup lang="ts">
import { useRouter } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import ModelSettings from '@/components/settings/ModelSettings.vue'
import { useI18n } from '@/i18n'

const router = useRouter()
const { locale, toggleLocale, t } = useI18n()
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
            <h1 class="text-lg font-semibold text-white">{{ t('model config') }}</h1>
            <p class="text-sm text-slate-400">{{ t('manage AI providers') }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="toggleLocale"
            class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
          >
            🌐 {{ locale === 'zh' ? 'EN' : '中文' }}
          </button>
          <button 
            @click="router.push('/')"
            class="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
            <span>{{ t('back to chat') }}</span>
          </button>
        </div>
      </header>
      
      <div class="flex-1 overflow-y-auto">
        <div class="max-w-4xl mx-auto p-8">
          <ModelSettings />
        </div>
      </div>
    </main>
  </div>
</template>
