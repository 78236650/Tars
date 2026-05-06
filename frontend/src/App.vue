<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const authStore = useAuthStore()
const settingsStore = useSettingsStore()

onMounted(async () => {
  await authStore.initAuth()
  await settingsStore.initSettings()
})
</script>

<template>
  <div class="min-h-screen bg-slate-900">
    <router-view />
  </div>
</template>