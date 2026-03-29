import { useState, useRef, useEffect, useMemo } from 'react'
import { Calendar, Building2, X } from 'lucide-react'
import { addDays, startOfWeek, addWeeks, format } from 'date-fns'
import { useCreateTask } from '../hooks/useCreateTask'
import { useAccounts } from '@/features/accounts/hooks/useAccounts'
import type { Priority } from '../types/tasks'

interface TaskQuickAddProps {
  isOpen: boolean
  onClose: () => void
  /** Pre-fill for "Create Follow-up" flow */
  prefill?: {
    title?: string
    accountId?: string
    accountName?: string
  }
}

export function TaskQuickAdd({ isOpen, onClose, prefill }: TaskQuickAddProps) {
  const createTask = useCreateTask()
  const inputRef = useRef<HTMLInputElement>(null)

  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [priority, setPriority] = useState<Priority>('medium')
  const [accountId, setAccountId] = useState<string | null>(null)
  const [accountName, setAccountName] = useState('')
  const [showDateOptions, setShowDateOptions] = useState(false)
  const [showAccountSearch, setShowAccountSearch] = useState(false)
  const [accountQuery, setAccountQuery] = useState('')

  const accountSearchRef = useRef<HTMLInputElement>(null)
  const dateRef = useRef<HTMLDivElement>(null)
  const accountRef = useRef<HTMLDivElement>(null)

  // Fetch accounts for searchable dropdown
  const { data: accountsData } = useAccounts({ limit: 100 })

  // Filter accounts by search query
  const filteredAccounts = useMemo(() => {
    if (!accountsData?.items) return []
    if (!accountQuery.trim()) return accountsData.items.slice(0, 8)
    const q = accountQuery.toLowerCase()
    return accountsData.items
      .filter((a) => a.name.toLowerCase().includes(q))
      .slice(0, 8)
  }, [accountsData, accountQuery])

  // Auto-focus input on open
  useEffect(() => {
    if (isOpen && inputRef.current) {
      const timer = setTimeout(() => inputRef.current?.focus(), 50)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  // Apply prefill values
  useEffect(() => {
    if (isOpen && prefill) {
      if (prefill.title) setTitle(prefill.title)
      if (prefill.accountId) setAccountId(prefill.accountId)
      if (prefill.accountName) setAccountName(prefill.accountName)
    }
  }, [isOpen, prefill])

  // Reset form on close
  useEffect(() => {
    if (!isOpen) {
      setTitle('')
      setDueDate('')
      setPriority('medium')
      setAccountId(null)
      setAccountName('')
      setShowDateOptions(false)
      setShowAccountSearch(false)
      setAccountQuery('')
    }
  }, [isOpen])

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dateRef.current && !dateRef.current.contains(e.target as Node)) {
        setShowDateOptions(false)
      }
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) {
        setShowAccountSearch(false)
        setAccountQuery('')
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Focus account search input when dropdown opens
  useEffect(() => {
    if (showAccountSearch && accountSearchRef.current) {
      accountSearchRef.current.focus()
    }
  }, [showAccountSearch])

  const handleSubmit = () => {
    const trimmed = title.trim()
    if (!trimmed) return
    if (createTask.isPending) return

    createTask.mutate(
      {
        title: trimmed,
        commitment_direction: 'yours',
        task_type: 'other',
        priority,
        trust_level: 'review',
        due_date: dueDate ? new Date(dueDate).toISOString() : undefined,
        account_id: accountId || undefined,
      },
      {
        onSuccess: () => {
          onClose()
        },
      },
    )
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

  // Quick date options
  const now = new Date()
  const dateOptions = [
    { label: 'Today', value: format(now, 'yyyy-MM-dd') },
    { label: 'Tomorrow', value: format(addDays(now, 1), 'yyyy-MM-dd') },
    {
      label: 'Next Monday',
      value: format(startOfWeek(addWeeks(now, 1), { weekStartsOn: 1 }), 'yyyy-MM-dd'),
    },
    { label: 'Next week', value: format(addDays(now, 7), 'yyyy-MM-dd') },
  ]

  const selectAccount = (id: string, name: string) => {
    setAccountId(id)
    setAccountName(name)
    setShowAccountSearch(false)
    setAccountQuery('')
  }

  const clearAccount = (e: React.MouseEvent) => {
    e.stopPropagation()
    setAccountId(null)
    setAccountName('')
  }

  const clearDate = (e: React.MouseEvent) => {
    e.stopPropagation()
    setDueDate('')
  }

  const priorityOptions: { value: Priority; label: string }[] = [
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
  ]

  return (
    <div
      style={{
        maxHeight: isOpen ? '400px' : '0px',
        opacity: isOpen ? 1 : 0,
        overflow: isOpen ? 'visible' : 'hidden',
        transition: 'max-height 200ms ease-in-out, opacity 200ms ease-in-out',
      }}
    >
      <div
        style={{
          background: 'var(--card-bg)',
          borderRadius: '12px',
          padding: '20px 24px',
          border: '2px solid rgba(233,77,53,0.2)',
          boxShadow: '0 0 0 4px rgba(233,77,53,0.05)',
          marginBottom: '24px',
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
          {/* Due date pill with dropdown */}
          <div ref={dateRef} className="relative">
            <button
              onClick={() => {
                setShowDateOptions(!showDateOptions)
                setShowAccountSearch(false)
              }}
              className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
              style={{
                fontSize: '12px',
                fontWeight: 500,
                color: dueDate ? 'var(--heading-text)' : 'var(--secondary-text)',
                background: dueDate ? 'rgba(233,77,53,0.06)' : 'var(--page-bg)',
                border: `1px solid ${dueDate ? 'rgba(233,77,53,0.15)' : 'var(--subtle-border)'}`,
                borderRadius: '9999px',
                padding: '4px 12px',
                cursor: 'pointer',
              }}
            >
              <Calendar className="size-3" />
              {dueDate
                ? format(new Date(dueDate), 'MMM d')
                : 'Due date'}
              {dueDate && (
                <span
                  onClick={clearDate}
                  className="ml-1 hover:text-red-500 transition-colors"
                  style={{ cursor: 'pointer' }}
                >
                  <X className="size-2.5" />
                </span>
              )}
            </button>

            {/* Date dropdown */}
            {showDateOptions && (
              <div
                className="absolute z-50"
                style={{
                  top: 'calc(100% + 4px)',
                  left: 0,
                  background: 'var(--card-bg)',
                  border: '1px solid var(--subtle-border)',
                  borderRadius: '8px',
                  boxShadow: '0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
                  padding: '4px',
                  minWidth: '160px',
                }}
              >
                {dateOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setDueDate(opt.value)
                      setShowDateOptions(false)
                    }}
                    className="w-full text-left transition-colors"
                    style={{
                      fontSize: '13px',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: 'none',
                      cursor: 'pointer',
                      color: dueDate === opt.value ? 'var(--brand-coral)' : 'var(--heading-text)',
                      background: dueDate === opt.value ? 'rgba(233,77,53,0.06)' : 'transparent',
                    }}
                    onMouseEnter={(e) => {
                      if (dueDate !== opt.value) e.currentTarget.style.background = 'var(--page-bg)'
                    }}
                    onMouseLeave={(e) => {
                      if (dueDate !== opt.value) e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    <span>{opt.label}</span>
                    <span
                      className="ml-2"
                      style={{ color: 'var(--secondary-text)', fontSize: '11px' }}
                    >
                      {format(new Date(opt.value), 'EEE, MMM d')}
                    </span>
                  </button>
                ))}
                {/* Custom date picker */}
                <div
                  style={{
                    borderTop: '1px solid var(--subtle-border)',
                    marginTop: '4px',
                    paddingTop: '4px',
                  }}
                >
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(e) => {
                      setDueDate(e.target.value)
                      setShowDateOptions(false)
                    }}
                    className="w-full"
                    style={{
                      fontSize: '12px',
                      padding: '6px 12px',
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--secondary-text)',
                      cursor: 'pointer',
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Account searchable select */}
          <div ref={accountRef} className="relative">
            <button
              onClick={() => {
                setShowAccountSearch(!showAccountSearch)
                setShowDateOptions(false)
              }}
              className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
              style={{
                fontSize: '12px',
                fontWeight: 500,
                color: accountId ? 'var(--heading-text)' : 'var(--secondary-text)',
                background: accountId ? 'rgba(59,130,246,0.06)' : 'var(--page-bg)',
                border: `1px solid ${accountId ? 'rgba(59,130,246,0.15)' : 'var(--subtle-border)'}`,
                borderRadius: '9999px',
                padding: '4px 12px',
                cursor: 'pointer',
              }}
            >
              <Building2 className="size-3" />
              {accountName || 'Account'}
              {accountId && (
                <span
                  onClick={clearAccount}
                  className="ml-1 hover:text-red-500 transition-colors"
                  style={{ cursor: 'pointer' }}
                >
                  <X className="size-2.5" />
                </span>
              )}
            </button>

            {/* Account search dropdown */}
            {showAccountSearch && (
              <div
                className="absolute z-50"
                style={{
                  top: 'calc(100% + 4px)',
                  left: 0,
                  background: 'var(--card-bg)',
                  border: '1px solid var(--subtle-border)',
                  borderRadius: '8px',
                  boxShadow: '0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
                  padding: '4px',
                  minWidth: '220px',
                  maxHeight: '260px',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {/* Search input */}
                <div
                  style={{
                    padding: '4px 8px 8px',
                    borderBottom: '1px solid var(--subtle-border)',
                  }}
                >
                  <input
                    ref={accountSearchRef}
                    value={accountQuery}
                    onChange={(e) => setAccountQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') {
                        e.stopPropagation()
                        setShowAccountSearch(false)
                        setAccountQuery('')
                      }
                      if (e.key === 'Enter' && filteredAccounts.length > 0) {
                        e.stopPropagation()
                        selectAccount(filteredAccounts[0].id, filteredAccounts[0].name)
                      }
                    }}
                    placeholder="Search accounts..."
                    className="w-full bg-transparent outline-none"
                    style={{
                      fontSize: '13px',
                      border: 'none',
                      padding: '4px',
                      color: 'var(--heading-text)',
                    }}
                  />
                </div>

                {/* Results */}
                <div style={{ overflow: 'auto', flex: 1 }}>
                  {filteredAccounts.length === 0 ? (
                    <p
                      style={{
                        fontSize: '12px',
                        color: 'var(--secondary-text)',
                        padding: '12px',
                        textAlign: 'center',
                        margin: 0,
                      }}
                    >
                      {accountQuery ? 'No accounts found' : 'No accounts yet'}
                    </p>
                  ) : (
                    filteredAccounts.map((account) => (
                      <button
                        key={account.id}
                        onClick={() => selectAccount(account.id, account.name)}
                        className="w-full text-left transition-colors"
                        style={{
                          fontSize: '13px',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: 'none',
                          cursor: 'pointer',
                          color:
                            accountId === account.id
                              ? 'var(--brand-coral)'
                              : 'var(--heading-text)',
                          background:
                            accountId === account.id
                              ? 'rgba(233,77,53,0.06)'
                              : 'transparent',
                        }}
                        onMouseEnter={(e) => {
                          if (accountId !== account.id)
                            e.currentTarget.style.background = 'var(--page-bg)'
                        }}
                        onMouseLeave={(e) => {
                          if (accountId !== account.id)
                            e.currentTarget.style.background = 'transparent'
                        }}
                      >
                        <div className="flex items-center gap-2">
                          <Building2
                            className="size-3 shrink-0"
                            style={{ color: 'var(--secondary-text)' }}
                          />
                          <span className="truncate">{account.name}</span>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

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

        {/* Footer: hint + loading state */}
        <div className="flex items-center justify-between" style={{ marginTop: '12px' }}>
          <p
            style={{
              fontSize: '11px',
              color: 'var(--secondary-text)',
              margin: 0,
            }}
          >
            Press Enter to create, Escape to cancel
          </p>
          {createTask.isPending && (
            <p
              style={{
                fontSize: '11px',
                color: 'var(--brand-coral)',
                margin: 0,
                fontWeight: 500,
              }}
            >
              Creating...
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
