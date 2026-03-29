import { useState, useRef, useEffect } from 'react'
import { Calendar, Building2 } from 'lucide-react'
import { useCreateTask } from '../hooks/useCreateTask'
import type { Priority } from '../types/tasks'

interface TaskQuickAddProps {
  isOpen: boolean
  onClose: () => void
}

export function TaskQuickAdd({ isOpen, onClose }: TaskQuickAddProps) {
  const createTask = useCreateTask()
  const inputRef = useRef<HTMLInputElement>(null)

  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [accountName, setAccountName] = useState('')
  const [showDatePicker, setShowDatePicker] = useState(false)
  const [showAccountInput, setShowAccountInput] = useState(false)

  // Auto-focus input on open
  useEffect(() => {
    if (isOpen && inputRef.current) {
      // Small delay to let animation start
      const timer = setTimeout(() => inputRef.current?.focus(), 50)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  // Reset form on close
  useEffect(() => {
    if (!isOpen) {
      setTitle('')
      setDueDate('')
      setPriority('medium')
      setAccountName('')
      setShowDatePicker(false)
      setShowAccountInput(false)
    }
  }, [isOpen])

  const handleSubmit = () => {
    const trimmed = title.trim()
    if (!trimmed) return

    createTask.mutate({
      title: trimmed,
      commitment_direction: 'yours',
      task_type: 'other',
      priority,
      trust_level: 'review',
      due_date: dueDate || undefined,
    })

    onClose()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  const priorityOptions: { value: Priority; label: string }[] = [
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
  ]

  return (
    <div
      style={{
        maxHeight: isOpen ? '300px' : '0px',
        opacity: isOpen ? 1 : 0,
        overflow: 'hidden',
        transition: 'max-height 200ms ease-in-out, opacity 200ms ease-in-out',
      }}
    >
      <div
        style={{
          background: 'var(--card-bg)',
          borderRadius: '12px',
          padding: '20px 24px',
          border: '1px solid var(--subtle-border)',
          marginBottom: '16px',
        }}
      >
        {/* Title input */}
        <input
          ref={inputRef}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What do you need to do?"
          className="w-full bg-transparent outline-none"
          style={{
            fontSize: '15px',
            fontWeight: 400,
            color: 'var(--heading-text)',
            border: 'none',
            padding: 0,
            marginBottom: '12px',
          }}
        />

        {/* Pill buttons row */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Due date pill */}
          {showDatePicker ? (
            <input
              type="date"
              value={dueDate}
              onChange={(e) => {
                setDueDate(e.target.value)
                setShowDatePicker(false)
              }}
              onBlur={() => setShowDatePicker(false)}
              autoFocus
              className="bg-transparent border rounded text-xs"
              style={{
                padding: '4px 8px',
                borderColor: 'var(--subtle-border)',
                color: 'var(--body-text)',
                fontSize: '12px',
              }}
            />
          ) : (
            <button
              onClick={() => setShowDatePicker(true)}
              className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
              style={{
                fontSize: '12px',
                fontWeight: 500,
                color: dueDate ? 'var(--body-text)' : 'var(--secondary-text)',
                background: 'var(--page-bg)',
                border: '1px solid var(--subtle-border)',
                borderRadius: '9999px',
                padding: '4px 12px',
                cursor: 'pointer',
              }}
            >
              <Calendar className="size-3" />
              {dueDate
                ? new Date(dueDate).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                  })
                : 'Due date'}
            </button>
          )}

          {/* Account pill */}
          {showAccountInput ? (
            <input
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              onBlur={() => setShowAccountInput(false)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === 'Escape') {
                  e.stopPropagation()
                  setShowAccountInput(false)
                }
              }}
              placeholder="Account name"
              autoFocus
              className="bg-transparent border rounded text-xs"
              style={{
                padding: '4px 8px',
                borderColor: 'var(--subtle-border)',
                color: 'var(--body-text)',
                fontSize: '12px',
                width: '140px',
              }}
            />
          ) : (
            <button
              onClick={() => setShowAccountInput(true)}
              className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
              style={{
                fontSize: '12px',
                fontWeight: 500,
                color: accountName ? 'var(--body-text)' : 'var(--secondary-text)',
                background: 'var(--page-bg)',
                border: '1px solid var(--subtle-border)',
                borderRadius: '9999px',
                padding: '4px 12px',
                cursor: 'pointer',
              }}
            >
              <Building2 className="size-3" />
              {accountName || 'Account'}
            </button>
          )}

          {/* Priority toggle */}
          <div
            className="inline-flex items-center"
            style={{
              background: 'var(--page-bg)',
              border: '1px solid var(--subtle-border)',
              borderRadius: '9999px',
              overflow: 'hidden',
            }}
          >
            {priorityOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPriority(opt.value)}
                className="transition-colors"
                style={{
                  fontSize: '12px',
                  fontWeight: 500,
                  padding: '4px 10px',
                  border: 'none',
                  cursor: 'pointer',
                  background:
                    priority === opt.value
                      ? opt.value === 'high'
                        ? 'rgba(239,68,68,0.1)'
                        : opt.value === 'medium'
                          ? 'rgba(245,158,11,0.1)'
                          : 'rgba(34,197,94,0.1)'
                      : 'transparent',
                  color:
                    priority === opt.value
                      ? opt.value === 'high'
                        ? '#EF4444'
                        : opt.value === 'medium'
                          ? '#D97706'
                          : '#22C55E'
                      : 'var(--secondary-text)',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Hint */}
        <p
          style={{
            fontSize: '11px',
            color: 'var(--secondary-text)',
            marginTop: '12px',
            marginBottom: 0,
          }}
        >
          Press Enter to create, Escape to cancel
        </p>
      </div>
    </div>
  )
}
