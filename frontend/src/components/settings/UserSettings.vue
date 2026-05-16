<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { authApi } from '@/api'
import AppSurfaceDialog from '@/components/common/AppSurfaceDialog.vue'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'

const authStore = useAuthStore()
const users = ref<User[]>([])
const showCreateModal = ref(false)
const showDeleteConfirm = ref(false)
const deletingUserId = ref('')
const newUser = ref({
  username: '',
  email: '',
  role: 'user',
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

const resetCreateForm = () => {
  newUser.value = {
    username: '',
    email: '',
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
  if (!newUser.value.username || !newUser.value.email) {
    return
  }

  try {
    await authApi.createUser(newUser.value.username, newUser.value.email, newUser.value.role)
    await loadUsers()
    closeCreateModal()
  } catch (error: any) {
    alert(error.response?.data?.message || 'Failed to create user')
  }
}

const deleteUser = async () => {
  try {
    await authApi.deleteUser(deletingUserId.value)
    await loadUsers()
    closeDeleteConfirm()
  } catch (error: any) {
    alert(error.response?.data?.message || 'Failed to delete user')
  }
}

const requestDelete = (userId: string) => {
  deletingUserId.value = userId
  showDeleteConfirm.value = true
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

onMounted(loadUsers)
</script>

<template>
  <div class="mx-auto max-w-4xl">
    <div class="rounded-xl bg-slate-800 p-6">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-white">User Management</h2>
        <button
          @click="showCreateModal = true"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
        >
          + Add User
        </button>
      </div>
      
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-slate-700">
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">User</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">Email</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">Role</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">Created</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-slate-400">Last Login</th>
              <th class="text-right py-3 px-4 text-sm font-medium text-slate-400">Actions</th>
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
                  :class="{
                    'bg-red-900/50 text-red-400': user.role === 'admin',
                    'bg-blue-900/50 text-blue-400': user.role === 'user',
                    'bg-gray-900/50 text-gray-400': user.role === 'guest'
                  }"
                >
                  {{ user.role.charAt(0).toUpperCase() + user.role.slice(1) }}
                </span>
              </td>
              <td class="py-4 px-4 text-slate-400 text-sm">{{ formatDate(user.created_at) }}</td>
              <td class="py-4 px-4 text-slate-400 text-sm">
                {{ user.last_login ? formatDate(user.last_login) : 'Never' }}
              </td>
              <td class="py-4 px-4 text-right">
                <button
                  @click="requestDelete(user.id)"
                  :disabled="user.id === authStore.user?.id"
                  class="text-sm text-red-400 hover:text-red-300 disabled:text-slate-600 disabled:cursor-not-allowed transition-colors"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        
        <div v-if="users.length === 0" class="text-center py-12 text-slate-500">
          <svg class="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
          </svg>
          <p>No users found</p>
        </div>
      </div>
    </div>

    <AppSurfaceDialog
      :open="showCreateModal"
      title="Create New User"
      description="Create a workspace user and assign an initial role."
      size="md"
      @close="closeCreateModal"
    >
      <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Username</label>
            <input
              v-model="newUser.username"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter username"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Email</label>
            <input
              v-model="newUser.email"
              type="email"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter email"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Role</label>
            <select
              v-model="newUser.role"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
              <option value="guest">Guest</option>
            </select>
          </div>
      </div>

      <template #footer>
        <div class="flex gap-3">
          <button
            @click="closeCreateModal"
            class="flex-1 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            @click="createUser"
            class="flex-1 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
          >
            Create
          </button>
        </div>
      </template>
    </AppSurfaceDialog>

    <AppSurfaceDialog
      :open="showDeleteConfirm"
      title="Confirm Deletion"
      :description="deletingUser ? `Delete ${deletingUser.username} from the workspace.` : 'Delete this user from the workspace.'"
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
            <h3 class="text-lg font-semibold text-white">Confirm Deletion</h3>
            <p class="text-sm text-slate-400">Are you sure you want to delete this user?</p>
          </div>
        </div>

      <template #footer>
        <div class="flex gap-3">
          <button
            @click="closeDeleteConfirm"
            class="flex-1 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            @click="deleteUser"
            class="flex-1 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white font-medium transition-colors"
          >
            Delete
          </button>
        </div>
      </template>
    </AppSurfaceDialog>
  </div>
</template>
