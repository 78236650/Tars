<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import LoginHeroPanel from '@/components/auth/LoginHeroPanel.vue'
import LoginCard from '@/components/auth/LoginCard.vue'
import WorkspaceJoinPanel from '@/components/auth/WorkspaceJoinPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const joinOpen = ref(false)
const submitError = ref('')

const onLoginSubmit = async (payload: { identifier: string; password: string; workspace: string }) => {
  const ok = await authStore.loginWithCredentials(payload.identifier, payload.password)

  if (!ok) {
    submitError.value = t('login.invalidCredentials')
    return
  }

  submitError.value = ''
  const workspace = payload.workspace.trim()
  await router.push(workspace ? `/?workspace=${encodeURIComponent(workspace)}` : '/')
}
</script>

<template>
  <div class="min-h-screen bg-[#0c0b09] px-6 py-8 text-white lg:px-10">
    <div class="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <LoginHeroPanel />
      <div class="space-y-4">
        <LoginCard :error-message="submitError" @submit="onLoginSubmit" @toggleJoin="joinOpen = !joinOpen" />
        <WorkspaceJoinPanel v-if="joinOpen" />
      </div>
    </div>
  </div>
</template>
