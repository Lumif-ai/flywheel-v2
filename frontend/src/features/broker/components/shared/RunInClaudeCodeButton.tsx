import { useState } from 'react'
import { toast } from 'sonner'

interface RunInClaudeCodeButtonProps {
  command: string
  label?: string
  variant?: 'default' | 'prominent'
  description?: string
}

export function RunInClaudeCodeButton({
  command,
  label = 'Run in Claude Code',
  variant = 'default',
  description,
}: RunInClaudeCodeButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleClick = async () => {
    await navigator.clipboard.writeText(command)
    setCopied(true)
    toast.success('Copied! Paste into Claude Code')
    setTimeout(() => setCopied(false), 2000)
  }

  const baseClasses = 'inline-flex items-center gap-1.5 rounded-lg text-sm font-medium transition-colors'
  const variantClasses = variant === 'prominent'
    ? 'bg-[#E94D35] text-white px-3 py-1.5 hover:bg-[#D4442F]'
    : 'border border-gray-200 text-gray-700 px-2.5 py-1 hover:bg-gray-50'

  return (
    <button onClick={handleClick} className={`${baseClasses} ${variantClasses}`} title={description || command}>
      {/* Terminal icon */}
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="4 17 10 11 4 5" />
        <line x1="12" y1="19" x2="20" y2="19" />
      </svg>
      {copied ? 'Copied!' : label}
    </button>
  )
}
