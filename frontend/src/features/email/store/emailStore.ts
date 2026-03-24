import { create } from 'zustand'

interface EmailState {
  selectedThreadId: string | null
  detailOpen: boolean
  alertDismissedIds: Set<string>
  selectThread: (id: string | null) => void
  closeDetail: () => void
  dismissAlert: (threadId: string) => void
}

export const useEmailStore = create<EmailState>((set) => ({
  selectedThreadId: null,
  detailOpen: false,
  alertDismissedIds: new Set<string>(),
  selectThread: (id) => set({ selectedThreadId: id, detailOpen: !!id }),
  closeDetail: () => set({ selectedThreadId: null, detailOpen: false }),
  dismissAlert: (threadId) =>
    set((s) => ({
      alertDismissedIds: new Set([...s.alertDismissedIds, threadId]),
    })),
}))
