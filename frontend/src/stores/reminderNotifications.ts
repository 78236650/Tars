import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { reminderNotificationsApi } from '@/api'
import type { ReminderNotification } from '@/types'

export const useReminderNotificationsStore = defineStore('reminderNotifications', () => {
  const items = ref<ReminderNotification[]>([])
  const total = ref(0)
  const unreadCount = ref(0)
  const limit = ref(20)
  const offset = ref(0)
  const selectedId = ref<string | null>(null)
  const selectedDetail = ref<ReminderNotification | null>(null)
  const isDrawerOpen = ref(false)
  const loadingList = ref(false)
  const loadingDetail = ref(false)
  const listLoaded = ref(false)
  const errorMessage = ref('')

  const hasNotifications = computed(() => items.value.length > 0)

  const upsertItem = (notification: ReminderNotification) => {
    const index = items.value.findIndex((item) => item.id === notification.id)
    if (index >= 0) {
      items.value[index] = {
        ...items.value[index],
        ...notification,
      }
      return
    }
    items.value.unshift(notification)
  }

  const syncCounters = (notifications: ReminderNotification[], totalValue?: number, unreadValue?: number) => {
    items.value = notifications
    total.value = typeof totalValue === 'number' ? totalValue : notifications.length
    unreadCount.value = typeof unreadValue === 'number'
      ? unreadValue
      : notifications.filter((item) => !item.is_read).length
  }

  const loadList = async (params?: { limit?: number; offset?: number }) => {
    loadingList.value = true
    errorMessage.value = ''
    try {
      const nextLimit = params?.limit ?? limit.value
      const nextOffset = params?.offset ?? offset.value
      const data = await reminderNotificationsApi.list({
        limit: nextLimit,
        offset: nextOffset,
      })
      limit.value = data.limit
      offset.value = data.offset
      syncCounters(data.notifications, data.total, data.unread_total)
      listLoaded.value = true
      if (selectedId.value) {
        const selected = data.notifications.find((item) => item.id === selectedId.value)
        if (selected && selectedDetail.value) {
          selectedDetail.value = {
            ...selectedDetail.value,
            ...selected,
          }
        }
      }
    } catch (error) {
      errorMessage.value = '加载提醒通知失败'
      throw error
    } finally {
      loadingList.value = false
    }
  }

  const openDrawer = async () => {
    isDrawerOpen.value = true
    await loadList()
  }

  const closeDrawer = () => {
    isDrawerOpen.value = false
  }

  const selectNotification = async (id: string) => {
    selectedId.value = id
    loadingDetail.value = true
    errorMessage.value = ''
    try {
      const detail = await reminderNotificationsApi.getDetail(id)
      upsertItem(detail)
      selectedDetail.value = detail
      if (!detail.is_read) {
        const readDetail = await reminderNotificationsApi.markRead(id)
        upsertItem(readDetail)
        selectedDetail.value = readDetail
      }
      unreadCount.value = items.value.filter((item) => !item.is_read).length
    } catch (error) {
      errorMessage.value = '加载通知详情失败'
      throw error
    } finally {
      loadingDetail.value = false
    }
  }

  const refreshAfterRealtimeReminder = async () => {
    await loadList()
    if (selectedId.value && selectedDetail.value) {
      const selected = items.value.find((item) => item.id === selectedId.value)
      if (selected) {
        selectedDetail.value = {
          ...selectedDetail.value,
          ...selected,
        }
      }
    }
  }

  const resetSelection = () => {
    selectedId.value = null
    selectedDetail.value = null
  }

  return {
    items,
    total,
    unreadCount,
    limit,
    offset,
    selectedId,
    selectedDetail,
    isDrawerOpen,
    loadingList,
    loadingDetail,
    listLoaded,
    errorMessage,
    hasNotifications,
    loadList,
    openDrawer,
    closeDrawer,
    selectNotification,
    refreshAfterRealtimeReminder,
    resetSelection,
  }
})
