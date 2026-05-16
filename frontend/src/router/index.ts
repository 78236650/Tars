import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: {
        desktopTitle: '聊天工作台',
        desktopSubtitle: '对话、计划、文件和提醒都在同一个主工作区完成。',
      }
    },
    {
      path: '/memory',
      name: 'memory',
      component: () => import('@/views/MemoryView.vue'),
      meta: {
        desktopTitle: '记忆工作台',
        desktopSubtitle: '用更清晰的结构管理人格、近期/长期记忆与压缩状态。',
      }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      redirect: '/settings/subagents',
      meta: {
        desktopTitle: '系统设置',
        desktopSubtitle: '集中管理子代理、用户和桌面工作台的基础配置。',
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
        }
      ]
    },
    {
      path: '/models',
      name: 'models',
      component: () => import('@/views/ModelsView.vue'),
      meta: {
        desktopTitle: '模型中心',
        desktopSubtitle: '统一切换本地与远端模型，管理端点与连通性。',
      }
    },
    {
      path: '/tools',
      name: 'tools',
      component: () => import('@/views/ToolsView.vue'),
      meta: {
        desktopTitle: '工具与技能',
        desktopSubtitle: '查看内置工具、已安装技能以及 SkillHub 生态。',
      }
    },
    {
      path: '/bi',
      name: 'bi',
      component: () => import('@/views/BiAnalyticsView.vue'),
      meta: {
        desktopTitle: 'BI 分析台',
        desktopSubtitle: '管理数据源、执行 SQL，并把结果转换为图表。',
      }
    },
    {
      path: '/meeting',
      name: 'meeting',
      component: () => import('@/views/MeetingView.vue'),
      meta: {
        desktopTitle: '会议工作台',
        desktopSubtitle: '录音、上传、转写与历史复盘整合到同一桌面流中。',
      }
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
      meta: {
        desktopTitle: '知识库',
        desktopSubtitle: '创建知识库、上传文档并直接验证检索效果。',
      }
    }
  ]
})

export default router
