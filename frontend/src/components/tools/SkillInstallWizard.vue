<script setup lang="ts">
import TrySkillButton from '@/components/tools/TrySkillButton.vue'
import { useI18n } from '@/i18n'
import BaseIcon from '@/components/common/BaseIcon.vue'

export interface InstallWizardState {
  skillId: string
  skillName: string
  success: boolean
  usage?: string
  examplePrompt?: string
  needsSetup?: boolean
  installHints?: string[]
  needsConfirmation?: boolean
  permissions?: string[]
  errorMessage?: string
}

const props = defineProps<{
  open: boolean
  state: InstallWizardState | null
  installing?: boolean
}>()

const emit = defineEmits<{
  close: []
  confirmPermissions: []
  skipSetupInstall: []
}>()

const { t } = useI18n()

const skillSlug = () => {
  const id = props.state?.skillId || ''
  return id.includes('/') ? id.split('/').pop() || id : id
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && state"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      @click.self="emit('close')"
    >
      <div class="w-full max-w-lg rounded-[28px] border border-amber-100/15 bg-surface-1 p-6 shadow-2xl">
        <div class="mb-5 flex items-start justify-between gap-4">
          <div>
            <p class="text-xs uppercase tracking-[0.2em] text-stone-500">
              {{ state.success ? t('tools.wizard.successTitle') : t('tools.wizard.setupTitle') }}
            </p>
            <h3 class="mt-2 text-xl font-semibold text-stone-100">{{ state.skillName }}</h3>
          </div>
          <button
            type="button"
            class="rounded-xl p-2 text-stone-400 transition hover:bg-white/[0.06] hover:text-stone-200"
            @click="emit('close')"
          >
            <BaseIcon icon="lucide:x" :size="20" />
          </button>
        </div>

        <div v-if="state.success" class="space-y-4">
          <div class="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-100">
            {{ state.usage || t('tools.installSuccess') }}
          </div>
          <div v-if="state.examplePrompt" class="rounded-2xl border border-amber-100/10 bg-white/[0.03] p-4">
            <p class="mb-2 text-xs uppercase tracking-[0.16em] text-stone-500">{{ t('tools.tryExample') }}</p>
            <p class="text-sm text-stone-200">「{{ state.examplePrompt }}」</p>
            <div class="mt-4">
              <TrySkillButton :prompt="state.examplePrompt" :skill="skillSlug()" />
            </div>
          </div>
          <ol class="space-y-2 text-sm text-stone-400">
            <li class="flex gap-2"><span class="text-amber-300">1.</span>{{ t('tools.wizard.stepChat') }}</li>
            <li class="flex gap-2"><span class="text-amber-300">2.</span>{{ t('tools.wizard.stepTry') }}</li>
            <li class="flex gap-2"><span class="text-amber-300">3.</span>{{ t('tools.wizard.stepManage') }}</li>
          </ol>
        </div>

        <div v-else-if="state.needsConfirmation" class="space-y-4">
          <p class="text-sm text-stone-300">{{ t('tools.permissionConfirm') }}</p>
          <ul class="list-disc space-y-1 pl-5 text-sm text-stone-400">
            <li v-for="perm in state.permissions || []" :key="perm">{{ perm }}</li>
          </ul>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="rounded-xl border border-amber-100/10 px-4 py-2 text-sm text-stone-300"
              @click="emit('close')"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950"
              :disabled="installing"
              @click="emit('confirmPermissions')"
            >
              {{ installing ? t('tools.installing') : t('tools.wizard.confirmInstall') }}
            </button>
          </div>
        </div>

        <div v-else-if="state.needsSetup" class="space-y-4">
          <p class="text-sm text-stone-300">{{ t('tools.needsSetup') }}</p>
          <ul class="list-disc space-y-1 pl-5 text-sm text-stone-400">
            <li v-for="hint in state.installHints || []" :key="hint">{{ hint }}</li>
          </ul>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="rounded-xl border border-amber-100/10 px-4 py-2 text-sm text-stone-300"
              @click="emit('close')"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950"
              :disabled="installing"
              @click="emit('skipSetupInstall')"
            >
              {{ installing ? t('tools.installing') : t('tools.wizard.installAnyway') }}
            </button>
          </div>
        </div>

        <div v-else class="space-y-4">
          <div class="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
            {{ state.errorMessage || t('tools.installFailed') }}
          </div>
          <div class="flex justify-end">
            <button
              type="button"
              class="rounded-xl border border-amber-100/10 px-4 py-2 text-sm text-stone-300"
              @click="emit('close')"
            >
              {{ t('common.close') }}
            </button>
          </div>
        </div>

        <div v-if="state.success" class="mt-6 flex justify-end">
          <button
            type="button"
            class="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-stone-950"
            @click="emit('close')"
          >
            {{ t('common.close') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
