import { useCallback, useRef } from 'react'
import type { GridApi, ColumnState } from 'ag-grid-community'

/**
 * Parameterized column persistence hook.
 * Saves/restores column widths, order, and visibility to localStorage.
 */
export function useColumnPersistence(storageKey: string) {
  const gridApiRef = useRef<GridApi | null>(null)

  const getSavedColumnState = useCallback((): ColumnState[] | null => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return null
      return JSON.parse(raw) as ColumnState[]
    } catch {
      return null
    }
  }, [storageKey])

  /** Call from onGridReady to restore saved column widths/order/visibility */
  const restoreColumnState = useCallback(
    (api: GridApi) => {
      const saved = getSavedColumnState()
      if (saved) {
        api.applyColumnState({ state: saved, applyOrder: true })
      }
    },
    [getSavedColumnState]
  )

  const onColumnStateChanged = useCallback(() => {
    const api = gridApiRef.current
    if (!api) return
    try {
      const state = api.getColumnState()
      localStorage.setItem(storageKey, JSON.stringify(state))
    } catch {
      // localStorage write failure -- non-fatal
    }
  }, [storageKey])

  return {
    restoreColumnState,
    onColumnStateChanged,
    gridApiRef,
  }
}
