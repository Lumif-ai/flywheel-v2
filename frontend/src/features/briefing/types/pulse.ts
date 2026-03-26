export interface PulseSignal {
  id: string
  type: 'reply_received' | 'followup_overdue' | 'bump_suggested'
  priority: 1 | 2 | 3
  account_id: string
  account_name: string
  title: string
  detail: string
  created_at: string
}

export interface PulseResponse {
  items: PulseSignal[]
  total: number
}
