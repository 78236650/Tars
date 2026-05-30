export interface VpBerth {
  id: string
  name: string
  length_m: number
  depth_m: number
  crane_count: number
  yard_zone: string
  position_x: number
  position_y: number
}

export interface VpHorizonRow {
  voyage_id: string
  vessel_name: string
  eta: string
  etb: string | null
  etd: string | null
  berth_id: string | null
  berth_name: string | null
  wait_min: number
  target_yard_zone: string
  cargo_teu: number
  locked: boolean
  agent_note?: string
}

export interface VpHorizonResponse {
  run_id?: string | null
  horizon_hours: number
  berths: VpBerth[]
  rows: VpHorizonRow[]
  agent_summary: string
  total_wait_min: number
  warnings: string[]
}

export interface VpVoyageDetail {
  voyage: {
    id: string
    vessel_name: string
    eta: string
    cargo_teu: number
    target_yard_zone: string
    service_hours: number
    length_m: number
    draft_m: number
    priority: number
  }
  assignment: {
    voyage_id: string
    berth_id: string | null
    berth_name: string | null
    etb: string | null
    etd: string | null
    wait_min: number
    locked: boolean
    source: string
  } | null
  alternatives: string[]
  timeline: { stage: string; time: string; detail: string }[]
}

export interface VpAdoptResult {
  task_ids: string[]
  goals: string[]
  count: number
}
