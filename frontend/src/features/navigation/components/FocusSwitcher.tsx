import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Crosshair, ChevronsUpDown, Plus, Check, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useFocusStore } from '@/stores/focus'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Focus } from '@/types/api'

export function FocusSwitcher() {
  const queryClient = useQueryClient()
  const activeFocus = useFocusStore((s) => s.activeFocus)
  const setActiveFocus = useFocusStore((s) => s.setActiveFocus)
  const setFocuses = useFocusStore((s) => s.setFocuses)
  const clearFocus = useFocusStore((s) => s.clearFocus)

  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [newFocusName, setNewFocusName] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const { data: focuses } = useQuery({
    queryKey: ['focuses'],
    queryFn: async () => {
      const data = await api.get<{ items: Focus[] }>('/focuses')
      setFocuses(data.items)
      return data.items
    },
  })

  const handleSwitch = async (focus: Focus) => {
    if (focus.id === activeFocus?.id) return
    try {
      await api.post(`/focuses/${focus.id}/switch`, {})
    } catch {
      // Switch may fail if not a member yet — join first
      try {
        await api.post(`/focuses/${focus.id}/join`, {})
        await api.post(`/focuses/${focus.id}/switch`, {})
      } catch {
        // Silently handle — focus still set locally
      }
    }
    setActiveFocus(focus)
    queryClient.invalidateQueries()
  }

  const handleClear = () => {
    clearFocus()
    queryClient.invalidateQueries()
  }

  const handleCreate = async () => {
    if (!newFocusName.trim()) return
    setIsCreating(true)
    try {
      const result = await api.post<{ focus: Focus }>('/focuses', {
        name: newFocusName.trim(),
      })
      await queryClient.invalidateQueries({ queryKey: ['focuses'] })
      setActiveFocus(result.focus)
      setIsCreateOpen(false)
      setNewFocusName('')
    } catch {
      // Handle error silently for now
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left hover:bg-muted transition-colors outline-none">
          <Crosshair className="size-4 text-muted-foreground shrink-0" />
          <span className="text-xs text-muted-foreground truncate flex-1">
            {activeFocus?.name ?? 'All Focuses'}
          </span>
          <ChevronsUpDown className="size-3 text-muted-foreground shrink-0" />
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" sideOffset={8} className="w-56">
          <DropdownMenuLabel>Focuses</DropdownMenuLabel>
          <DropdownMenuItem
            onClick={handleClear}
            className="flex items-center gap-2"
          >
            <X className="size-3.5 text-muted-foreground shrink-0" />
            <span className="text-sm flex-1">All Focuses</span>
            {!activeFocus && (
              <Check className="size-3.5 text-primary shrink-0" />
            )}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {focuses?.map((focus) => (
            <DropdownMenuItem
              key={focus.id}
              onClick={() => handleSwitch(focus)}
              className="flex items-center gap-2"
            >
              <Crosshair className="size-3.5 text-muted-foreground shrink-0" />
              <span className="text-sm truncate flex-1">{focus.name}</span>
              {focus.id === activeFocus?.id && (
                <Check className="size-3.5 text-primary shrink-0" />
              )}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-2 text-muted-foreground"
          >
            <Plus className="size-4" />
            <span>Create focus</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Focus</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input
              placeholder="Focus name"
              value={newFocusName}
              onChange={(e) => setNewFocusName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreate()
              }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateOpen(false)
                setNewFocusName('')
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!newFocusName.trim() || isCreating}
            >
              {isCreating ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
