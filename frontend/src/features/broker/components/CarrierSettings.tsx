import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { ArrowLeft, Plus, Edit2, Power } from 'lucide-react'
import { toast } from 'sonner'
import { useCarriers } from '../hooks/useCarriers'
import { useCreateCarrier, useUpdateCarrier, useDeleteCarrier } from '../hooks/useCarrierMutations'
import type { CarrierConfig, UpdateCarrierPayload } from '../types/broker'
import { CarrierForm, type CarrierFormState, EMPTY_FORM, carrierToForm, formToPayload } from './CarrierForm'

export function CarrierSettings() {
  const { data: carriers, isLoading } = useCarriers()
  const createMutation = useCreateCarrier()
  const updateMutation = useUpdateCarrier()
  const deleteMutation = useDeleteCarrier()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingCarrier, setEditingCarrier] = useState<CarrierConfig | null>(null)
  const [form, setForm] = useState<CarrierFormState>(EMPTY_FORM)
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(null)

  function openCreate() {
    setEditingCarrier(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  function openEdit(carrier: CarrierConfig) {
    setEditingCarrier(carrier)
    setForm(carrierToForm(carrier))
    setDialogOpen(true)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload = formToPayload(form)

    if (editingCarrier) {
      updateMutation.mutate(
        { id: editingCarrier.id, payload: payload as UpdateCarrierPayload },
        {
          onSuccess: () => {
            toast.success('Carrier updated')
            setDialogOpen(false)
          },
          onError: () => toast.error('Failed to update carrier'),
        },
      )
    } else {
      createMutation.mutate(payload, {
        onSuccess: () => {
          toast.success('Carrier added')
          setDialogOpen(false)
        },
        onError: () => toast.error('Failed to add carrier'),
      })
    }
  }

  function handleDeactivate(id: string) {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success('Carrier deactivated')
        setConfirmDeactivate(null)
      },
      onError: () => toast.error('Failed to deactivate carrier'),
    })
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-60" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/broker" className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-2xl font-semibold">Carrier Settings</h1>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" />
          Add Carrier
        </Button>
      </div>

      {/* Table */}
      {!carriers || carriers.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          No carriers configured yet. Click "Add Carrier" to get started.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">Name</th>
                <th className="px-3 py-2 text-left font-medium">Type</th>
                <th className="px-3 py-2 text-left font-medium">Submission</th>
                <th className="px-3 py-2 text-left font-medium">Coverage Types</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {carriers.map((carrier) => (
                <tr key={carrier.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{carrier.carrier_name}</td>
                  <td className="px-3 py-2 capitalize">{carrier.carrier_type}</td>
                  <td className="px-3 py-2 capitalize">{carrier.submission_method}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(carrier.coverage_types ?? []).slice(0, 3).map((ct) => (
                        <Badge key={ct} variant="outline" className="text-xs">
                          {ct}
                        </Badge>
                      ))}
                      {(carrier.coverage_types ?? []).length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{carrier.coverage_types.length - 3}
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <Badge
                      variant="outline"
                      className={
                        carrier.is_active
                          ? 'bg-green-50 text-green-700 border-0'
                          : 'bg-gray-50 text-gray-500 border-0'
                      }
                    >
                      {carrier.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(carrier)}>
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                      {carrier.is_active && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-orange-600 hover:text-orange-700"
                          onClick={() => setConfirmDeactivate(carrier.id)}
                        >
                          <Power className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingCarrier ? 'Edit Carrier' : 'Add Carrier'}</DialogTitle>
          </DialogHeader>
          <CarrierForm
            form={form}
            onChange={setForm}
            onSubmit={handleSubmit}
            isSubmitting={createMutation.isPending || updateMutation.isPending}
            submitLabel={editingCarrier ? 'Save Changes' : 'Add Carrier'}
          />
        </DialogContent>
      </Dialog>

      {/* Deactivate Confirmation Dialog */}
      <Dialog open={!!confirmDeactivate} onOpenChange={() => setConfirmDeactivate(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Deactivate Carrier?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This carrier will no longer appear in matching results. You can reactivate it later.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDeactivate(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => confirmDeactivate && handleDeactivate(confirmDeactivate)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deactivating...' : 'Deactivate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
