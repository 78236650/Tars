<script setup lang="ts">
import { ref } from 'vue'
import { skillsApi } from '@/api'
import { useI18n } from '@/i18n'

const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()

const form = ref({
  id: '',
  name: '',
  description: '',
  prompt_template: '',
  tags: '',
})
const loading = ref(false)
const error = ref('')

const isValid = () => form.value.id.trim() && form.value.name.trim() && form.value.prompt_template.trim()

const submit = async () => {
  if (!isValid()) {
    error.value = t('addSkill.fillRequired')
    return
  }
  loading.value = true
  error.value = ''
  try {
    await skillsApi.createPromptSkill({
      id: form.value.id.trim(),
      name: form.value.name.trim(),
      description: form.value.description.trim(),
      prompt_template: form.value.prompt_template,
      tags: form.value.tags.split(',').map(s => s.trim()).filter(Boolean),
    })
    emit('close')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || t('addSkill.createFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="emit('close')"></div>

    <div class="relative bg-slate-800 rounded-xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <h2 class="text-xl font-semibold text-white">{{ t('addSkill.title') }}</h2>
        <button @click="emit('close')" class="p-2 hover:bg-slate-700 rounded-lg">
          <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <div class="flex-1 overflow-y-auto p-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('addSkill.id') }} <span class="text-red-400">*</span></label>
          <input
            v-model="form.id"
            type="text"
            :placeholder="t('addSkill.idPlaceholder')"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('addSkill.name') }} <span class="text-red-400">*</span></label>
          <input
            v-model="form.name"
            type="text"
            :placeholder="t('addSkill.namePlaceholder')"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('addSkill.description') }}</label>
          <input
            v-model="form.description"
            type="text"
            :placeholder="t('addSkill.descPlaceholder')"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('addSkill.tags') }}</label>
          <input
            v-model="form.tags"
            type="text"
            :placeholder="t('addSkill.tagsPlaceholder')"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('addSkill.template') }} <span class="text-red-400">*</span></label>
          <textarea
            v-model="form.prompt_template"
            rows="8"
            :placeholder="t('addSkill.templatePlaceholder')"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          ></textarea>
          <p class="text-xs text-slate-500 mt-1">{{ t('addSkill.templateHint') }}</p>
        </div>

        <div v-if="error" class="p-3 bg-red-900/50 text-red-400 rounded-lg text-sm">{{ error }}</div>
      </div>

      <div class="px-6 py-4 border-t border-slate-700 flex justify-end gap-3">
        <button @click="emit('close')" class="px-4 py-2 text-slate-400 hover:text-white transition-colors">{{ t('common.cancel') }}</button>
        <button
          @click="submit"
          :disabled="loading || !isValid()"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
        >{{ loading ? t('addSkill.creating') : t('common.create') }}</button>
      </div>
    </div>
  </div>
</template>
