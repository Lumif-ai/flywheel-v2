import { useEffect, useRef, useCallback } from 'react'

interface UseTaskKeyboardNavOptions {
  enabled: boolean
  onSelect: (taskId: string) => void
}

const FOCUS_CLASS = 'task-card-focused'

function isInputElement(el: Element | null): boolean {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

function getTaskCards(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('[data-task-id]'))
}

export function useTaskKeyboardNav({ enabled, onSelect }: UseTaskKeyboardNavOptions) {
  const focusedIndexRef = useRef(-1)

  const clearFocusRing = useCallback(() => {
    const prev = document.querySelector(`.${FOCUS_CLASS}`)
    if (prev) prev.classList.remove(FOCUS_CLASS)
  }, [])

  const applyFocusRing = useCallback((el: HTMLElement) => {
    clearFocusRing()
    el.classList.add(FOCUS_CLASS)
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [clearFocusRing])

  useEffect(() => {
    if (!enabled) {
      clearFocusRing()
      focusedIndexRef.current = -1
      return
    }

    function handleKeyDown(e: KeyboardEvent) {
      // Don't fire when typing in form elements
      if (isInputElement(document.activeElement)) return

      const cards = getTaskCards()
      if (cards.length === 0) return

      if (e.key === 'j') {
        e.preventDefault()
        const next = focusedIndexRef.current + 1
        if (next >= cards.length) return // don't wrap
        focusedIndexRef.current = next
        applyFocusRing(cards[next])
      } else if (e.key === 'k') {
        e.preventDefault()
        const prev = focusedIndexRef.current - 1
        if (prev < 0) return // don't wrap
        focusedIndexRef.current = prev
        applyFocusRing(cards[prev])
      } else if (e.key === 'Enter' || e.key === ' ') {
        if (focusedIndexRef.current < 0 || focusedIndexRef.current >= cards.length) return
        e.preventDefault()
        const card = cards[focusedIndexRef.current]
        const taskId = card.getAttribute('data-task-id')
        if (taskId) onSelect(taskId)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      clearFocusRing()
      focusedIndexRef.current = -1
    }
  }, [enabled, onSelect, applyFocusRing, clearFocusRing])
}
