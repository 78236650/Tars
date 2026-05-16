<script setup lang="ts">
import { ref } from 'vue'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
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
  <AppSurfaceDialog
    :open="true"
    :title="t('addSkill.title')"
    size="xl"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div>
        <label class="mb-2 block text-sm font-medium text-stone-200">{{ t('addSkill.id') }} <span class="text-red-400">*</span></label>
        <input
          v-model="form.id"
          type="text"
          :placeholder="t('addSkill.idPlaceholder')"
          class="w-full rounded-2xl border border-amber-100/10 bg-[#110f0d] px-3 py-2 text-stone-100 placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400/40"
        />
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-stone-200">{{ t('addSkill.name') }} <span class="text-red-400">*</span></label>
        <input
          v-model="form.name"
          type="text"
          :placeholder="t('addSkill.namePlaceholder')"
          class="w-full rounded-2xl border border-amber-100/10 bg-[#110f0d] px-3 py-2 text-stone-100 placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400/40"
        />
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-stone-200">{{ t('addSkill.description') }}</label>
        <input
          v-model="form.description"
          type="text"
          :placeholder="t('addSkill.descPlaceholder')"
          class="w-full rounded-2xl border border-amber-100/10 bg-[#110f0d] px-3 py-2 text-stone-100 placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400/40"
        />
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-stone-200">{{ t('addSkill.tags') }}</label>
        <input
          v-model="form.tags"
          type="text"
          :placeholder="t('addSkill.tagsPlaceholder')"
          class="w-full rounded-2xl border border-amber-100/10 bg-[#110f0d] px-3 py-2 text-stone-100 placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400/40"
        />
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-stone-200">{{ t('addSkill.template') }} <span class="text-red-400">*</span></label>
        <textarea
          v-model="form.prompt_template"
          rows="8"
          :placeholder="t('addSkill.templatePlaceholder')"
          class="w-full resize-none rounded-2xl border border-amber-100/10 bg-[#110f0d] px-3 py-2 font-mono text-sm text-stone-100 placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400/40"
        ></textarea>
        <p class="mt-1 text-xs text-stone-500">{{ t('addSkill.templateHint') }}</p>
      </div>

      <div v-if="error" class="rounded-2xl border border-red-500/20 bg-red-950/40 p-3 text-sm text-red-300">{{ error }}</div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <button
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-4 py-2 text-stone-200 transition-colors hover:bg-white/[0.08]"
          @click="emit('close')"
        >{{ t('common.cancel') }}</button>
        <button
          type="button"
          @click="submit"
          :disabled="loading || !isValid()"
          class="rounded-2xl bg-amber-400 px-4 py-2 font-medium text-stone-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-stone-600 disabled:text-stone-300"
        >{{ loading ? t('addSkill.creating') : t('common.create') }}</button>
      </div>
    </template>
  </AppSurfaceDialog>
</template>
