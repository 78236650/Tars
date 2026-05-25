<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import DesktopShell from '@/components/layout/DesktopShell.vue'
import ToastHost from '@/components/common/ToastHost.vue'

const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const isLoading = ref(!authStore.restoreFromCache())
const route = useRoute()
const showShell = computed(() => route.meta.shell !== false)

onMounted(async () => {
  try {
    await authStore.initAuth()
    if (authStore.isAuthenticated) {
      await settingsStore.initSettings()
    } else {
      await settingsStore.loadModels()
    }
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
    <ToastHost />
    <DesktopShell v-if="showShell">
      <KeepAlive include="ChatView">
        <component :is="Component" />
      </KeepAlive>
    </DesktopShell>
    <component :is="Component" v-else />
  </RouterView>
</template>
