import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: {
        desktopTitleKey: 'desktop.chat.title',
        desktopSubtitleKey: 'desktop.chat.subtitle',
      }
    },
    {
      path: '/memory',
      name: 'memory',
      component: () => import('@/views/MemoryView.vue'),
      meta: {
        desktopTitleKey: 'desktop.memory.title',
        desktopSubtitleKey: 'desktop.memory.subtitle',
      }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      redirect: '/settings/subagents',
      meta: {
        desktopTitleKey: 'desktop.settings.title',
        desktopSubtitleKey: 'desktop.settings.subtitle',
      },
      children: [
        {
          path: 'subagents',
          name: 'settings-subagents',
          component: () => import('@/components/settings/SubAgentSettings.vue')
        },
        {
          path: 'users',
          name: 'settings-users',
          component: () => import('@/components/settings/UserSettings.vue')
        },
        {
          path: 'personality',
          name: 'settings-personality',
          component: () => import('@/components/settings/PersonalitySettings.vue')
        }
      ]
    },
    {
      path: '/models',
      name: 'models',
      component: () => import('@/views/ModelsView.vue'),
      meta: {
        desktopTitleKey: 'desktop.models.title',
        desktopSubtitleKey: 'desktop.models.subtitle',
      }
    },
    {
      path: '/tools',
      name: 'tools',
      component: () => import('@/views/ToolsView.vue'),
      meta: {
        desktopTitleKey: 'desktop.tools.title',
        desktopSubtitleKey: 'desktop.tools.subtitle',
      }
    },
    {
      path: '/bi',
      name: 'bi',
      component: () => import('@/views/BiAnalyticsView.vue'),
      meta: {
        desktopTitleKey: 'desktop.bi.title',
        desktopSubtitleKey: 'desktop.bi.subtitle',
      }
    },
    {
      path: '/meeting',
      name: 'meeting',
      component: () => import('@/views/MeetingView.vue'),
      meta: {
        desktopTitleKey: 'desktop.meeting.title',
        desktopSubtitleKey: 'desktop.meeting.subtitle',
      }
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
      meta: {
        desktopTitleKey: 'desktop.knowledge.title',
        desktopSubtitleKey: 'desktop.knowledge.subtitle',
      }
    }
  ]
})

export default router
