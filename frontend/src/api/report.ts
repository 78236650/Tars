import { apiClient } from './index'

export interface ChartSpecDef {
  chart_type: string
  dimensions: { field: string }[]
  measures: { field: string; agg: string }[]
  filters?: { field: string; op: string; value: unknown }[]
  limit?: number
  granularity?: string
}

export interface ChartSeries {
  name: string
  data: unknown[]
}

export interface ChartData {
  categories: string[]
  series: ChartSeries[]
  truncated: boolean
}

export interface SavedChart {
  id: string
  datasource_id: string
  name: string
  chart_type: string
  spec: ChartSpecDef
}

export const reportApi = {
  chartTypes: () =>
    apiClient.get<{ chart_types: string[] }>('/report/chart-types').then((r) => r.data.chart_types),
  listCharts: (datasourceId: string) =>
    apiClient.get<{ charts: SavedChart[] }>('/report/charts', { params: { datasource_id: datasourceId } })
      .then((r) => r.data.charts),
  createChart: (body: { datasource_id: string; table_name: string; name: string; chart_type: string; spec: ChartSpecDef }) =>
    apiClient.post<SavedChart>('/report/charts', body).then((r) => r.data),
  deleteChart: (id: string) =>
    apiClient.delete(`/report/charts/${id}`).then((r) => r.data),
  executeChart: (body: { datasource_id: string; table_name: string; spec: ChartSpecDef }) =>
    apiClient.post<ChartData>('/report/charts/execute', body).then((r) => r.data),
}
