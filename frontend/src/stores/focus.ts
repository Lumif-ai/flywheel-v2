import { create } from 'zustand'
import type { Focus } from '@/types/api'

interface FocusState {
  activeFocus: Focus | null
  focuses: Focus[]
  setActiveFocus: (focus: Focus | null) => void
  setFocuses: (focuses: Focus[]) => void
  clearFocus: () => void
}

export const useFocusStore = create<FocusState>((set) => ({
  activeFocus: null,
  focuses: [],
  setActiveFocus: (activeFocus) => set({ activeFocus }),
  setFocuses: (focuses) => set({ focuses }),
  clearFocus: () => set({ activeFocus: null }),
}))
