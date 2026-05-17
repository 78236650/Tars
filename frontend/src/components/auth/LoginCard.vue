<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from '@/i18n'
import AuthFeedbackAlert from './AuthFeedbackAlert.vue'

const props = withDefaults(defineProps<{ errorMessage?: string }>(), {
  errorMessage: '',
})

const emit = defineEmits<{
  submit: [payload: { identifier: string; password: string; workspace: string }]
  toggleJoin: []
}>()

const { t } = useI18n()
const form = reactive({
  identifier: '',
  password: '',
  workspace: '',
})
const errorMessage = ref('')
const visibleErrorMessage = computed(() => errorMessage.value || props.errorMessage)

const onSubmit = () => {
  if (!form.identifier || !form.password) {
    errorMessage.value = t('login.validationRequired')
    return
  }

  errorMessage.value = ''
  emit('submit', { ...form })
}
</script>

<template>
  <section class="rounded-[32px] border border-amber-100/10 bg-[#171310] p-8 shadow-[0_32px_100px_rgba(0,0,0,0.35)]">
    <p class="text-sm uppercase tracking-[0.24em] text-amber-300">{{ t('login.cardEyebrow') }}</p>
    <h2 class="mt-3 text-3xl font-semibold text-stone-50">{{ t('login.cardTitle') }}</h2>
    <p class="mt-2 text-sm text-stone-400">{{ t('login.cardSubtitle') }}</p>

    <div class="mt-6 space-y-4">
      <input
        v-model="form.identifier"
        class="w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100"
        :placeholder="t('login.identifierPlaceholder')"
      />
      <input
        v-model="form.password"
        type="password"
        class="w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100"
        :placeholder="t('login.passwordPlaceholder')"
      />
      <input
        v-model="form.workspace"
        class="w-full rounded-2xl border border-amber-100/10 bg-black/10 px-4 py-3 text-stone-100"
        :placeholder="t('login.workspacePlaceholder')"
      />

      <AuthFeedbackAlert v-if="visibleErrorMessage" tone="error" :message="visibleErrorMessage" />

      <button
        class="w-full rounded-2xl bg-amber-500 px-4 py-3 font-medium text-stone-950"
        type="button"
        @click="onSubmit"
      >
        {{ t('login.submit') }}
      </button>

      <div class="grid grid-cols-2 gap-3">
        <button
          class="rounded-2xl border border-amber-100/10 px-4 py-3 text-sm text-stone-100"
          type="button"
          @click="$emit('toggleJoin')"
        >
          {{ t('login.joinWorkspace') }}
        </button>
        <button class="rounded-2xl border border-amber-100/10 px-4 py-3 text-sm text-stone-100" type="button">
          {{ t('login.forgotPassword') }}
        </button>
      </div>
    </div>
  </section>
</template>
