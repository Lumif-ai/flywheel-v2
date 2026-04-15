import type { ICellRendererParams } from 'ag-grid-community'
import { toast } from 'sonner'

export function ClauseLink(props: ICellRendererParams) {
  const { value } = props

  if (!value) {
    return (
      <div className="flex items-center h-full">
        <span style={{ fontSize: '11px', color: '#D1D5DB' }}>&mdash;</span>
      </div>
    )
  }

  const text = String(value)
  const truncated = text.length > 60 ? text.slice(0, 60) + '...' : text

  const handleClick = async () => {
    await navigator.clipboard.writeText(text)
    toast.success('Clause copied')
  }

  return (
    <div className="flex items-center h-full">
      <span
        title={text}
        onClick={handleClick}
        style={{ color: '#E94D35', cursor: 'pointer' }}
      >
        {truncated}
      </span>
    </div>
  )
}
