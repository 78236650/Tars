import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      children: [
        {
          path: '',
          name: 'settings-personality',
          component: () => import('@/components/settings/PersonalitySettings.vue')
        },
        {
          path: 'subagents',
          name: 'settings-subagents',
          component: () => import('@/components/settings/SubAgentSettings.vue')
        },
        {
          path: 'users',
          name: 'settings-users',
          component: () => import('@/components/settings/UserSettings.vue')
        }
      ]
    },
    {
      path: '/models',
      name: 'models',
      component: () => import('@/views/ModelsView.vue')
    },
    {
      path: '/tools',
      name: 'tools',
      component: () => import('@/views/ToolsView.vue')
    },
    {
    path: '/bi',
    name: 'bi',
    component: () => import('@/views/BiAnalyticsView.vue')
  },
  {
    path: '/meeting',
    name: 'meeting',
    component: () => import('@/views/MeetingView.vue')
  },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue')
    }
  ]
})

export default router