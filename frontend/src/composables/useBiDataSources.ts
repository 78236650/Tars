import { ref } from 'vue'
import { biApi } from '@/api'
import type { DataSource } from '@/types'

const datasources = ref<DataSource[]>([])
const loadError = ref('')
const loading = ref(false)

export function useBiDataSources() {
  async function loadDataSources(): Promise<DataSource[]> {
    loading.value = true
    loadError.value = ''
    try {
      const res = await biApi.listDataSources()
      datasources.value = res.datasources
      return res.datasources
    } catch (e: any) {
      const status = e.response?.status
      if (status === 403) {
        loadError.value = 'bi.accessDenied'
      } else if (status === 404 || status === 503) {
        loadError.value = 'bi.moduleDisabled'
      } else {
        loadError.value = e.response?.data?.detail || 'bi.loadFailed'
      }
      datasources.value = []
      return []
    } finally {
      loading.value = false
    }
  }

  return {
    datasources,
    loadError,
    loading,
    loadDataSources,
  }
}
