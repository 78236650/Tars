<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const authStore = useAuthStore()
const settingsStore = useSettingsStore()

onMounted(async () => {
  try {
    await authStore.initAuth()
    await settingsStore.initSettings()
  } catch (e) {
    console.error('[App] 启动初始化失败', e)
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-900">
    <router-view />
  </div>
</template>