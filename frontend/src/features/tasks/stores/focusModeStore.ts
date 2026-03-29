import { create } from 'zustand'

export type AnimationDirection = 'left' | 'right' | 'down' | null

interface FocusModeState {
  currentIndex: number
  animationDirection: AnimationDirection
  isEditing: boolean
  isComplete: boolean
  nextTask: (direction: AnimationDirection) => void
  setEditing: (editing: boolean) => void
  setComplete: () => void
  setAnimationDirection: (direction: AnimationDirection) => void
  reset: () => void
}

export const useFocusModeStore = create<FocusModeState>((set) => ({
  currentIndex: 0,
  animationDirection: null,
  isEditing: false,
  isComplete: false,

  nextTask: (direction) =>
    set((s) => ({
      currentIndex: s.currentIndex + 1,
      animationDirection: direction,
      isEditing: false,
    })),

  setEditing: (editing) => set({ isEditing: editing }),

  setComplete: () => set({ isComplete: true }),

  setAnimationDirection: (direction) => set({ animationDirection: direction }),

  reset: () =>
    set({
      currentIndex: 0,
      animationDirection: null,
      isEditing: false,
      isComplete: false,
    }),
}))
