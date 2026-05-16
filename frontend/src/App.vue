<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import DesktopShell from '@/components/layout/DesktopShell.vue'

const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const isLoading = ref(true)

onMounted(async () => {
  try {
    await authStore.initAuth()
    await settingsStore.loadModels()
  } catch {
    console.warn('Initialization failed')
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div v-if="isLoading" class="h-screen w-screen bg-slate-900 flex items-center justify-center">
    <div class="text-center">
      <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
      <p class="text-slate-400">Loading...</p>
    </div>
  </div>
  <RouterView v-else v-slot="{ Component }">
    <DesktopShell>
      <component :is="Component" />
    </DesktopShell>
  </RouterView>
</template>
