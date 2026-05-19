<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { rolesApi, authApi, type RoleTemplate } from '@/api'
import { useI18n } from '@/i18n'
import type { User } from '@/types'
import AppSurfaceDrawer from '@/components/common/AppSurfaceDrawer.vue'
import { resolveTemplateId, templateDisplayName } from '@/utils/roleDisplay'

const props = defineProps<{ open: boolean; user: User | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()

const templates = ref<RoleTemplate[]>([])
const selectedTemplateId = ref('')
const username = ref('')
const email = ref('')
const newPassword = ref('')
const saving = ref(false)

const selectedTemplate = computed(() =>
  templates.value.find(t => t.id === selectedTemplateId.value)
)

watch(() => props.user, (u) => {
  if (u) {
    username.value = u.username
    email.value = u.email
    selectedTemplateId.value = resolveTemplateId(u)
    newPassword.value = ''
  }
}, { immediate: true })

watch(() => props.open, async (open) => {
  if (open && templates.value.length === 0) {
    try { templates.value = await rolesApi.list() } catch {}
  }
})

function templateLabel(id: string): string {
  return templateDisplayName(id, t, templates.value)
}

function templateDesc(id: string): string {
  const key = `role.${id}.desc`
  const desc = t(key)
  return desc !== key ? desc : ''
}

const toolsPreview = computed(() => {
  const tmpl = selectedTemplate.value
  if (!tmpl) return ''
  if (tmpl.allowed_tools === '*') return t('role.admin.desc')
  return (tmpl.allowed_tools as string[]).join(', ')
})

const modulesPreview = computed(() => {
  const tmpl = selectedTemplate.value
  if (!tmpl) return ''
  return tmpl.allowed_modules.length ? tmpl.allowed_modules.join(', ') : '—'
})

async function save() {
  if (!props.user) return
  saving.value = true
  try {
    // Update basic info
    if (username.value !== props.user.username || email.value !== props.user.email) {
      await authApi.updateUser(props.user.id, { username: username.value, email: email.value })
    }
    // Reset password
    if (newPassword.value) {
      await authApi.updateUser(props.user.id, { password: newPassword.value } as any)
    }
    // Assign role template
    const currentTemplate = resolveTemplateId(props.user)
    if (selectedTemplateId.value !== currentTemplate) {
      await rolesApi.assignRole(props.user.id, selectedTemplateId.value)
    }
    emit('saved')
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <AppSurfaceDrawer :open="open" :title="t('userEdit.title')" @close="emit('close')">
    <div class="p-6 space-y-6">
      <h2 class="text-lg font-semibold text-stone-100">{{ t('userEdit.title') }}: {{ user?.username }}</h2>

      <!-- 基本信息 -->
      <section>
        <h3 class="text-sm font-medium text-stone-400 mb-3">{{ t('userEdit.basicInfo') }}</h3>
        <div class="space-y-3">
          <input v-model="username" class="w-full bg-white/[0.04] border border-amber-100/10 rounded-lg px-3 py-2 text-stone-200 focus:outline-none focus:border-amber-300/30" :placeholder="t('userSettings.usernamePlaceholder')" />
          <input v-model="email" type="email" class="w-full bg-white/[0.04] border border-amber-100/10 rounded-lg px-3 py-2 text-stone-200 focus:outline-none focus:border-amber-300/30" :placeholder="t('userSettings.emailPlaceholder')" />
          <input v-model="newPassword" type="password" class="w-full bg-white/[0.04] border border-amber-100/10 rounded-lg px-3 py-2 text-stone-200 focus:outline-none focus:border-amber-300/30" :placeholder="t('userEdit.newPasswordPlaceholder')" />
        </div>
      </section>

      <!-- 角色模板选择 -->
      <section>
        <h3 class="text-sm font-medium text-stone-400 mb-3">{{ t('role.selectTemplate') }}</h3>
        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="tmpl in templates"
            :key="tmpl.id"
            @click="selectedTemplateId = tmpl.id"
            class="relative rounded-lg border p-3 text-left transition"
            :class="selectedTemplateId === tmpl.id
              ? 'border-amber-400/50 bg-amber-500/10'
              : 'border-amber-100/10 bg-white/[0.02] hover:border-amber-300/20'"
          >
            <div class="text-sm font-medium text-stone-200">{{ templateLabel(tmpl.id) }}</div>
            <div class="text-xs text-stone-500 mt-0.5">{{ templateDesc(tmpl.id) }}</div>
            <span v-if="selectedTemplateId === tmpl.id" class="absolute top-2 right-2 w-2 h-2 rounded-full bg-amber-400"></span>
          </button>
        </div>
      </section>

      <!-- 权限预览 -->
      <section v-if="selectedTemplate">
        <h3 class="text-sm font-medium text-stone-400 mb-3">{{ t('role.permissionPreview') }}</h3>
        <div class="rounded-lg border border-amber-100/10 bg-white/[0.02] p-3 space-y-2 text-xs">
          <div><span class="text-stone-500">{{ t('role.tools') }}:</span> <span class="text-stone-300">{{ toolsPreview }}</span></div>
          <div><span class="text-stone-500">{{ t('role.modules') }}:</span> <span class="text-stone-300">{{ modulesPreview }}</span></div>
          <div v-if="selectedTemplate.denied_tools?.length"><span class="text-stone-500">{{ t('role.denied') }}:</span> <span class="text-rose-300">{{ selectedTemplate.denied_tools.join(', ') }}</span></div>
          <div><span class="text-stone-500">{{ t('role.maxConcurrent') }}:</span> <span class="text-stone-300">{{ selectedTemplate.max_concurrent }}</span></div>
        </div>
      </section>

      <!-- 操作按钮 -->
      <div class="flex justify-end gap-3 pt-2">
        <button @click="emit('close')" class="px-4 py-2 rounded-lg border border-amber-100/10 text-stone-400 hover:text-stone-200 transition">{{ t('common.cancel') }}</button>
        <button @click="save" :disabled="saving" class="px-4 py-2 rounded-lg bg-amber-500 text-stone-950 font-medium hover:bg-amber-400 disabled:opacity-50 transition">{{ t('role.saveAndApply') }}</button>
      </div>
    </div>
  </AppSurfaceDrawer>
</template>
