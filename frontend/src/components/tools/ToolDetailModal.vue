<script setup lang="ts">
import { computed, ref } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import BaseIcon from '@/components/common/BaseIcon.vue'
import { skillsApi } from '@/api'
import { useI18n } from '@/i18n'

const props = defineProps<{
  tool: {
    id: string
    name: string
    icon?: string
    type: string
    source?: string
    status?: string
    description: string
    usage?: string
    config?: Record<string, any>
    default_config?: Record<string, any>
    prompt_template?: string
    parameters?: { name: string; type: string; description: string; required: boolean; default?: any }[]
    version?: string
    author?: string
    tags?: string[]
    permissions?: string[]
    enabled?: boolean
  }
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()

const loading = ref(false)
const message = ref<{ type: 'success' | 'error'; text: string } | null>(null)

const isSkill = computed(() => props.tool.type === 'plugin' || props.tool.type === 'prompt')
const isPromptSkill = computed(() => props.tool.type === 'prompt')
const isEnabled = computed(() => props.tool.enabled !== false && props.tool.status !== 'disabled')

const typeLabel = computed(() => {
  switch (props.tool.type) {
    case 'builtin':
      return t('toolDetail.builtin')
    case 'plugin':
      return t('toolDetail.plugin')
    case 'prompt':
      return t('toolDetail.prompt')
    default:
      return props.tool.type
  }
})

const typeClass = computed(() => {
  switch (props.tool.type) {
    case 'builtin':
      return 'bg-blue-600/20 text-blue-400'
    case 'plugin':
      return 'bg-green-600/20 text-green-400'
    case 'prompt':
      return 'bg-purple-600/20 text-purple-400'
    default:
      return 'bg-slate-600/20 text-slate-400'
  }
})

const toggleEnabled = async () => {
  loading.value = true
  message.value = null
  try {
    if (isEnabled.value) {
      await skillsApi.disableSkill(props.tool.id)
      message.value = { type: 'success', text: t('toolDetail.disabledMsg') }
    } else {
      await skillsApi.enableSkill(props.tool.id)
      message.value = { type: 'success', text: t('toolDetail.enabledMsg') }
    }
    setTimeout(() => emit('close'), 800)
  } catch {
    message.value = { type: 'error', text: t('toolDetail.operationFailed') }
  } finally {
    loading.value = false
  }
}

const deleteSkill = async () => {
  if (!confirm(t('toolDetail.uninstallConfirm'))) return
  loading.value = true
  try {
    await skillsApi.deleteSkill(props.tool.id)
    message.value = { type: 'success', text: t('toolDetail.uninstalled') }
    setTimeout(() => emit('close'), 800)
  } catch {
    message.value = { type: 'error', text: t('toolDetail.operationFailed') }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AppSurfaceDialog
    :open="true"
    :title="tool.name"
    :description="tool.description"
    size="xl"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <div class="flex items-start gap-3">
        <span class="text-3xl"><BaseIcon v-if="tool.icon" :icon="tool.icon" :size="32" /><BaseIcon v-else icon="lucide:wrench" :size="32" /></span>
        <div class="min-w-0">
          <div class="mt-1 flex flex-wrap items-center gap-2">
            <span class="rounded-full px-2 py-0.5 text-xs" :class="typeClass">{{ typeLabel }}</span>
            <span v-if="tool.version" class="text-xs text-stone-500">v{{ tool.version }}</span>
            <span v-if="tool.author" class="text-xs text-stone-500">by {{ tool.author }}</span>
          </div>
        </div>
      </div>

      <div v-if="tool.tags && tool.tags.length > 0">
        <h3 class="mb-2 text-sm font-medium text-stone-400">{{ t('toolDetail.tags') }}</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="tag in tool.tags"
            :key="tag"
            class="rounded-full border border-amber-100/10 bg-white/[0.04] px-2 py-1 text-xs text-stone-300"
          >{{ tag }}</span>
        </div>
      </div>

      <div v-if="isPromptSkill && tool.prompt_template">
        <h3 class="mb-2 text-sm font-medium text-stone-400">{{ t('toolDetail.promptTemplate') }}</h3>
        <pre class="max-h-48 overflow-x-auto overflow-y-auto whitespace-pre-wrap rounded-2xl border border-amber-100/10 bg-surface-0 p-4 text-sm text-stone-300">{{ tool.prompt_template }}</pre>
      </div>

      <div v-if="tool.parameters && tool.parameters.length > 0">
        <h3 class="mb-2 text-sm font-medium text-stone-400">{{ t('toolDetail.parameters') }}</h3>
        <div class="space-y-2">
          <div
            v-for="param in tool.parameters"
            :key="param.name"
            class="rounded-2xl border border-amber-100/10 bg-surface-0 p-3"
          >
            <div class="flex items-center gap-2">
              <span class="font-mono text-sm text-stone-100">{{ param.name }}</span>
              <span class="rounded bg-white/[0.04] px-1.5 py-0.5 text-xs text-stone-400">{{ param.type }}</span>
              <span v-if="param.required" class="text-xs text-red-400">{{ t('toolDetail.required') }}</span>
            </div>
            <p v-if="param.description" class="mt-1 text-sm text-stone-400">{{ param.description }}</p>
            <p v-if="param.default !== undefined && param.default !== null" class="mt-1 text-xs text-stone-500">
              {{ t('toolDetail.defaultValue') }}: {{ param.default }}
            </p>
          </div>
        </div>
      </div>

      <div v-if="tool.permissions && tool.permissions.length > 0">
        <h3 class="mb-2 text-sm font-medium text-stone-400">{{ t('toolDetail.permissions') }}</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="perm in tool.permissions"
            :key="perm"
            class="rounded border border-yellow-700 px-2 py-1 text-xs text-yellow-400 bg-yellow-900/30"
          >{{ perm }}</span>
        </div>
      </div>

      <div v-if="tool.usage">
        <h3 class="mb-2 text-sm font-medium text-stone-400">{{ t('toolDetail.usage') }}</h3>
        <pre class="overflow-x-auto rounded-2xl border border-amber-100/10 bg-surface-0 p-4 text-sm text-stone-300">{{ tool.usage }}</pre>
      </div>

      <div
        v-if="message"
        class="rounded-2xl border p-3"
        :class="message.type === 'success' ? 'border-green-500/20 bg-green-950/40 text-green-300' : 'border-red-500/20 bg-red-950/40 text-red-300'"
      >
        {{ message.text }}
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-between gap-4">
        <button
          v-if="isSkill && tool.source !== 'builtin'"
          type="button"
          :disabled="loading"
          class="rounded-2xl border border-red-500/20 bg-red-950/40 px-4 py-2 text-red-300 transition-colors hover:bg-red-900/50 disabled:opacity-50"
          @click="deleteSkill"
        >{{ t('common.uninstall') }}</button>
        <div v-else></div>

        <div class="flex items-center justify-end gap-3">
          <button
            type="button"
            class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition-colors hover:bg-white/[0.08]"
            @click="emit('close')"
          >{{ t('common.close') }}</button>
          <button
            v-if="isSkill"
            type="button"
            :disabled="loading"
            class="rounded-2xl px-4 py-2 font-medium transition-colors disabled:opacity-50"
            :class="isEnabled ? 'bg-white/[0.08] text-stone-100 hover:bg-white/[0.12]' : 'bg-amber-400 text-stone-950 hover:bg-amber-300'"
            @click="toggleEnabled"
          >{{ isEnabled ? t('common.disable') : t('common.enable') }}</button>
        </div>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
