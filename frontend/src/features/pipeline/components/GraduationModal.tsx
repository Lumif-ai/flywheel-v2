import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useGraduate } from '../hooks/useGraduate'
import { colors, typography } from '@/lib/design-tokens'

interface GraduationModalProps {
  accountId: string
  accountName: string
  open: boolean
  onClose: () => void
}

interface TypeOption {
  key: string
  label: string
  description: string
}

const TYPE_OPTIONS: TypeOption[] = [
  { key: 'customer', label: 'Customer', description: 'A paying or potential paying client' },
  { key: 'advisor', label: 'Advisor', description: 'Someone who provides guidance and expertise' },
  { key: 'investor', label: 'Investor', description: 'A financial backer or funding source' },
]

export function GraduationModal({ accountId, accountName, open, onClose }: GraduationModalProps) {
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const graduate = useGraduate()

  const toggleType = (key: string) => {
    setSelectedTypes((prev) =>
      prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]
    )
  }

  // Entity level auto-detection: person if only advisor or investor, company otherwise
  const entityLevel =
    selectedTypes.length > 0 &&
    selectedTypes.every((t) => t === 'advisor' || t === 'investor') &&
    !selectedTypes.includes('customer')
      ? 'person'
      : 'company'

  const handleSubmit = () => {
    graduate.mutate(
      { id: accountId, types: selectedTypes, entity_level: entityLevel },
      {
        onSuccess: () => {
          setSelectedTypes([])
          onClose()
        },
      }
    )
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setSelectedTypes([])
      onClose()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>Graduate {accountName}</DialogTitle>
          <DialogDescription>
            Select relationship type(s) for this account
          </DialogDescription>
        </DialogHeader>

        {/* Type selection cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', margin: '4px 0' }}>
          {TYPE_OPTIONS.map(({ key, label, description }) => {
            const isSelected = selectedTypes.includes(key)
            return (
              <label
                key={key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: `1px solid ${isSelected ? 'var(--brand-coral)' : colors.subtleBorder}`,
                  background: isSelected ? 'var(--brand-tint-warm, rgba(233,77,53,0.06))' : colors.cardBg,
                  cursor: 'pointer',
                  transition: 'border-color 150ms, background 150ms',
                }}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleType(key)}
                  style={{ accentColor: 'var(--brand-coral)', cursor: 'pointer', flexShrink: 0 }}
                />
                <div>
                  <div
                    style={{
                      fontSize: typography.caption.size,
                      fontWeight: 600,
                      color: isSelected ? 'var(--brand-coral)' : colors.headingText,
                    }}
                  >
                    {label}
                  </div>
                  <div
                    style={{
                      fontSize: '12px',
                      color: colors.secondaryText,
                      marginTop: '2px',
                    }}
                  >
                    {description}
                  </div>
                </div>
              </label>
            )
          })}
        </div>

        <DialogFooter>
          <Button
            onClick={handleSubmit}
            disabled={selectedTypes.length === 0 || graduate.isPending}
            style={{
              background: selectedTypes.length > 0 ? 'var(--brand-coral)' : undefined,
              color: selectedTypes.length > 0 ? '#fff' : undefined,
            }}
          >
            {graduate.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Graduate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
