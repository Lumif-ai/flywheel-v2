import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { ICellEditorParams } from 'ag-grid-community'
import { X } from 'lucide-react'

export const DatePickerEditor = forwardRef(
  (props: ICellEditorParams, ref) => {
    const inputRef = useRef<HTMLInputElement>(null)
    const [value, setValue] = useState<string>(props.value ?? '')

    useImperativeHandle(ref, () => ({
      getValue() {
        return value || null
      },
      isPopup() {
        return true
      },
    }))

    useEffect(() => {
      const input = inputRef.current
      if (!input) return
      input.focus()
      try {
        input.showPicker()
      } catch {
        // showPicker() not supported in all browsers
      }
    }, [])

    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          gap: '4px',
          background: '#FFFFFF',
          padding: '4px',
          border: '1px solid #E5E7EB',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <input
          ref={inputRef}
          type="date"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          style={{
            border: '1px solid #E5E7EB',
            borderRadius: '6px',
            padding: '4px 8px',
            fontSize: '13px',
            outline: 'none',
            color: '#121212',
            background: '#FFFFFF',
          }}
        />
        <button
          onClick={() => setValue('')}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '20px',
            height: '20px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            borderRadius: '4px',
            padding: 0,
          }}
          title="Clear date"
        >
          <X style={{ width: '16px', height: '16px', color: '#9CA3AF' }} />
        </button>
      </div>
    )
  }
)

DatePickerEditor.displayName = 'DatePickerEditor'
