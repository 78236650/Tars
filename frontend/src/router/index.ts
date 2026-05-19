import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: {
        public: true,
        shell: false,
      }
    },
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.chat.title',
        desktopSubtitleKey: 'desktop.chat.subtitle',
      }
    },
    {
      path: '/memory',
      name: 'memory',
      component: () => import('@/views/MemoryView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.memory.title',
        desktopSubtitleKey: 'desktop.memory.subtitle',
      }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      redirect: '/settings/personality',
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.settings.title',
        desktopSubtitleKey: 'desktop.settings.subtitle',
      },
      children: [
        {
          path: 'personality',
          name: 'settings-personality',
          component: () => import('@/components/settings/PersonalitySettings.vue')
        },
        {
          path: 'subagents',
          name: 'settings-subagents',
          component: () => import('@/components/settings/SubAgentSettings.vue')
        },
        {
          path: 'changelog',
          name: 'settings-changelog',
          component: () => import('@/components/settings/ChangelogView.vue')
        },
      ]
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      redirect: '/admin/users',
      meta: {
        requiresAuth: true,
        requiresAdmin: true,
        desktopTitleKey: 'desktop.admin.title',
        desktopSubtitleKey: 'desktop.admin.subtitle',
      },
      children: [
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('@/components/settings/UserSettings.vue')
        },
        {
          path: 'roles',
          name: 'admin-roles',
          component: () => import('@/views/RolesView.vue')
        },
        {
          path: 'audit',
          name: 'admin-audit',
          component: () => import('@/views/AuditView.vue')
        },
      ]
    },
    {
      path: '/models',
      name: 'models',
      component: () => import('@/views/ModelsView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.models.title',
        desktopSubtitleKey: 'desktop.models.subtitle',
      }
    },
    {
      path: '/tools',
      name: 'tools',
      component: () => import('@/views/ToolsView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.tools.title',
        desktopSubtitleKey: 'desktop.tools.subtitle',
      }
    },
    {
      path: '/bi',
      name: 'bi',
      component: () => import('@/views/BiAnalyticsView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.bi.title',
        desktopSubtitleKey: 'desktop.bi.subtitle',
      }
    },
    {
      path: '/meeting',
      name: 'meeting',
      component: () => import('@/views/MeetingView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.meeting.title',
        desktopSubtitleKey: 'desktop.meeting.subtitle',
      }
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
      meta: {
        requiresAuth: true,
        desktopTitleKey: 'desktop.knowledge.title',
        desktopSubtitleKey: 'desktop.knowledge.subtitle',
      }
    },
  ]
})

router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.meta.public && authStore.isAuthenticated) {
    return '/'
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }

  if (to.meta.requiresAdmin && authStore.user?.role !== 'admin') {
    return '/'
  }

  return true
})

export default router
