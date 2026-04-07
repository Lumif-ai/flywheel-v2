import { useRef, useState } from 'react'

export interface QuickAddRowProps {
  onAdd: (name: string) => void
}

export function QuickAddRow({ onAdd }: QuickAddRowProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const trimmed = value.trim()
      if (trimmed) {
        onAdd(trimmed)
        setValue('')
      }
    } else if (e.key === 'Escape') {
      setValue('')
      inputRef.current?.blur()
    }
  }

  return (
    <div style={{ borderTop: '1px solid #F3F4F6', padding: '8px 12px' }}>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="+ Add company or person..."
        style={{
          width: '100%',
          border: 'none',
          outline: 'none',
          fontSize: '13px',
          color: '#121212',
          background: 'transparent',
        }}
      />
    </div>
  )
}
