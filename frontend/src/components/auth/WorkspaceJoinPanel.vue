<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from '@/i18n'
import AuthFeedbackAlert from './AuthFeedbackAlert.vue'

const { t } = useI18n()
const inviteCode = ref('')
const errorMessage = ref('')

const applyInvite = () => {
  if (!inviteCode.value.trim()) {
    errorMessage.value = t('login.inviteRequired')
    return
  }

  errorMessage.value = ''
}
</script>

<template>
  <section class="rounded-[28px] border border-amber-100/10 bg-surface-1 p-5">
    <p class="text-sm font-medium text-stone-100">{{ t('login.joinWorkspace') }}</p>
    <p class="mt-2 text-sm text-stone-400">{{ t('login.joinDescription') }}</p>
    <input
      v-model="inviteCode"
      class="mt-4 w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100"
      :placeholder="t('login.invitePlaceholder')"
    />
    <AuthFeedbackAlert v-if="errorMessage" class="mt-4" tone="error" :message="errorMessage" />
    <div class="mt-4 flex gap-3">
      <button class="rounded-2xl bg-amber-500 px-4 py-3 font-medium text-stone-950" type="button" @click="applyInvite">
        {{ t('login.applyInvite') }}
      </button>
      <button class="rounded-2xl border border-amber-100/10 px-4 py-3 text-sm text-stone-100" type="button">
        {{ t('login.contactAdmin') }}
      </button>
    </div>
  </section>
</template>
