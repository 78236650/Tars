<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { authApi, rolesApi, type RoleTemplate } from '@/api'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import UserEditDrawer from './UserEditDrawer.vue'
import { useI18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'
import { resolveTemplateId, roleBadgeClass, templateDisplayName } from '@/utils/roleDisplay'

const authStore = useAuthStore()
const { locale, t } = useI18n()
const users = ref<User[]>([])
const showCreateModal = ref(false)
const showDeleteConfirm = ref(false)
const deletingUserId = ref('')
const editingUser = ref<User | null>(null)
const showEditDrawer = ref(false)

// v4.0.2: 角色模板
const roleTemplates = ref<RoleTemplate[]>([])
const showRoleAssign = ref(false)
const assignTargetUserId = ref('')
const assigningRoleId = ref('')
const newUser = ref({
  username: '',
  email: '',
  password: '',
  role: 'standard',
})

const deletingUser = computed(() => users.value.find((user) => user.id === deletingUserId.value) ?? null)

const loadUsers = async () => {
  try {
    const response = await authApi.getUsers()
    users.value = response.users
  } catch {
    users.value = []
  }
}

const loadRoleTemplates = async () => {
  try {
    roleTemplates.value = await rolesApi.list()
  } catch {
    roleTemplates.value = []
  }
}

const displayRoleName = (user: User): string =>
  templateDisplayName(resolveTemplateId(user), t, roleTemplates.value)

const openRoleAssign = (user: User) => {
  assignTargetUserId.value = user.id
  assigningRoleId.value = resolveTemplateId(user)
  showRoleAssign.value = true
}

const closeRoleAssign = () => {
  showRoleAssign.value = false
  assignTargetUserId.value = ''
  assigningRoleId.value = ''
}

const assignRole = async () => {
  if (!assignTargetUserId.value || !assigningRoleId.value) return
  try {
    await rolesApi.assignRole(assignTargetUserId.value, assigningRoleId.value)
    await loadUsers()
    closeRoleAssign()
  } catch (e) {
    console.error('角色分配失败:', e)
  }
}

const isAdmin = computed(() => authStore.user?.role === 'admin')

const resetCreateForm = () => {
  newUser.value = {
    username: '',
    email: '',
    password: '',
    role: 'user',
  }
}

const closeCreateModal = () => {
  showCreateModal.value = false
  resetCreateForm()
}

const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingUserId.value = ''
}

const createUser = async () => {
  if (!newUser.value.username || !newUser.value.email || !newUser.value.password) {
    return
  }

  try {
    await authApi.createUser(
      newUser.value.username,
      newUser.value.email,
      newUser.value.password,
      newUser.value.role
    )
    await loadUsers()
    closeCreateModal()
  } catch (error: any) {
    alert(error.response?.data?.message || t('userSettings.createFailed'))
  }
}

const deleteUser = async () => {
  try {
    await authApi.deleteUser(deletingUserId.value)
    await loadUsers()
    closeDeleteConfirm()
  } catch (error: any) {
    alert(error.response?.data?.message || t('userSettings.deleteFailed'))
  }
}

const requestDelete = (userId: string) => {
  deletingUserId.value = userId
  showDeleteConfirm.value = true
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const dateLocale = locale.value === 'zh' ? 'zh-CN' : 'en-US'
  return date.toLocaleDateString(dateLocale, { month: 'short', day: 'numeric', year: 'numeric' })
}

onMounted(() => {
  loadUsers()
  loadRoleTemplates()
})
</script>

<template>
  <div class="mx-auto max-w-4xl">
    <div class="rounded-xl bg-slate-800 p-6">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-white">{{ t('userSettings.title') }}</h2>
        <button
          @click="showCreateModal = true"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
        >
          + {{ t('userSettings.addUser') }}
        </button>
      </div>
      
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-slate-700">
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">{{ t('userSettings.columns.user') }}</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">{{ t('userSettings.columns.email') }}</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">{{ t('userSettings.columns.role') }}</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">{{ t('userSettings.columns.created') }}</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">{{ t('userSettings.columns.lastLogin') }}</th>
              <th class="text-right py-3 px-4 text-sm font-medium text-slate-400">{{ t('userSettings.columns.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in users"
              :key="user.id"
              class="border-b border-slate-700 hover:bg-slate-700/50 transition-colors"
            >
              <td class="py-4 px-4">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 bg-slate-700 rounded-full flex items-center justify-center">
                    <span class="text-white font-medium">{{ user.username.charAt(0).toUpperCase() }}</span>
                  </div>
                  <div>
                    <p class="text-white font-medium">{{ user.username }}</p>
                    <p class="text-xs text-slate-400">{{ user.id.slice(0, 8) }}...</p>
                  </div>
                </div>
              </td>
              <td class="py-4 px-4 text-slate-300">{{ user.email }}</td>
              <td class="py-4 px-4">
                <span
                  class="px-2 py-1 rounded-full text-xs font-medium"
                  :class="roleBadgeClass(user)"
                >
                  {{ displayRoleName(user) }}
                </span>
              </td>
              <td class="py-4 px-4 text-slate-400 text-sm">{{ formatDate(user.created_at) }}</td>
              <td class="py-4 px-4 text-slate-400 text-sm">
                {{ user.last_login ? formatDate(user.last_login) : t('userSettings.never') }}
              </td>
              <td class="py-4 px-4 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button
                    v-if="isAdmin"
                    @click="editingUser = user; showEditDrawer = true"
                    class="text-sm text-amber-400 hover:text-amber-300 transition-colors"
                  >
                    {{ t('common.edit') }}
                  </button>
                  <button
                    @click="requestDelete(user.id)"
                    :disabled="user.id === authStore.user?.id"
                    class="text-sm text-red-400 hover:text-red-300 disabled:text-slate-600 disabled:cursor-not-allowed transition-colors"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        
        <div v-if="users.length === 0" class="text-center py-12 text-slate-500">
          <svg class="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
          </svg>
          <p>{{ t('userSettings.empty') }}</p>
        </div>
      </div>
    </div>

    <AppSurfaceDialog
      :open="showCreateModal"
      :title="t('userSettings.createTitle')"
      :description="t('userSettings.createDescription')"
      size="md"
      @close="closeCreateModal"
    >
      <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('userSettings.username') }}</label>
            <input
              v-model="newUser.username"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              :placeholder="t('userSettings.usernamePlaceholder')"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('userSettings.email') }}</label>
            <input
              v-model="newUser.email"
              type="email"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              :placeholder="t('userSettings.emailPlaceholder')"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('userSettings.initialPassword') }}</label>
            <input
              v-model="newUser.password"
              type="password"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              :placeholder="t('userSettings.initialPasswordPlaceholder')"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">{{ t('role.selectTemplate') }}</label>
            <select
              v-model="newUser.role"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="tmpl in roleTemplates" :key="tmpl.id" :value="tmpl.id">
                {{ t(`role.${tmpl.id}`) !== `role.${tmpl.id}` ? t(`role.${tmpl.id}`) : tmpl.name }}
              </option>
              <option v-if="!roleTemplates.length" value="user">{{ t('userSettings.roles.user') }}</option>
              <option v-if="!roleTemplates.length" value="admin">{{ t('userSettings.roles.admin') }}</option>
              <option v-if="!roleTemplates.length" value="guest">{{ t('userSettings.roles.guest') }}</option>
            </select>
          </div>
      </div>

      <template #footer>
        <div class="flex gap-3">
          <button
            @click="closeCreateModal"
            class="flex-1 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white font-medium transition-colors"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="createUser"
            class="flex-1 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
          >
            {{ t('common.create') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <!-- v4.0.2: 角色分配弹窗 -->
    <AppSurfaceDialog
      :open="showRoleAssign"
      :title="t('userSettings.assignRoleTitle')"
      :description="t('userSettings.assignRoleDesc')"
      size="md"
      @close="closeRoleAssign"
    >
      <div class="space-y-3">
        <p class="text-sm text-slate-400">{{ t('userSettings.selectRoleTemplate') }}</p>
        <div class="space-y-2 max-h-60 overflow-y-auto">
          <button
            v-for="tmpl in roleTemplates"
            :key="tmpl.id"
            @click="assigningRoleId = tmpl.id"
            class="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition border"
            :class="assigningRoleId === tmpl.id
              ? 'bg-amber-500/15 border-amber-500/30 text-amber-200'
              : 'border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-600'"
          >
            <span class="text-lg">{{ tmpl.id === 'admin' ? '🔒' : tmpl.id === 'developer' ? '💻' : tmpl.id === 'analyst' ? '📊' : tmpl.id === 'operator' ? '🔧' : tmpl.id === 'standard' ? '👤' : tmpl.id === 'readonly' ? '👁️' : '📝' }}</span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium">{{ tmpl.name }}</p>
              <p class="text-xs text-slate-400 truncate">{{ tmpl.description }}</p>
            </div>
            <span
              v-if="assigningRoleId === tmpl.id"
              class="text-amber-400 text-sm"
            >✓</span>
          </button>
        </div>
      </div>

      <template #footer>
        <div class="flex gap-3">
          <button
            @click="closeRoleAssign"
            class="flex-1 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white font-medium transition-colors"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="assignRole"
            :disabled="!assigningRoleId"
            class="flex-1 py-2 bg-amber-500 hover:bg-amber-400 rounded-lg text-stone-950 font-medium transition-colors disabled:opacity-50"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <AppSurfaceDialog
      :open="showDeleteConfirm"
      :title="t('userSettings.deleteTitle')"
      :description="
        deletingUser
          ? t('userSettings.deleteUserDescription', { username: deletingUser.username })
          : t('userSettings.deleteDescription')
      "
      size="sm"
      @close="closeDeleteConfirm"
    >
      <div class="flex items-center gap-3">
          <div class="w-12 h-12 bg-red-900/50 rounded-full flex items-center justify-center">
            <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <div>
            <h3 class="text-lg font-semibold text-white">{{ t('userSettings.deleteTitle') }}</h3>
            <p class="text-sm text-slate-400">{{ t('userSettings.deletePrompt') }}</p>
          </div>
        </div>

      <template #footer>
        <div class="flex gap-3">
          <button
            @click="closeDeleteConfirm"
            class="flex-1 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white font-medium transition-colors"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="deleteUser"
            class="flex-1 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white font-medium transition-colors"
          >
            {{ t('common.delete') }}
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <UserEditDrawer
      :open="showEditDrawer"
      :user="editingUser"
      @close="showEditDrawer = false; editingUser = null"
      @saved="showEditDrawer = false; editingUser = null; loadUsers()"
    />
  </div>
</template>
