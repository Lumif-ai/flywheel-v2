import { useState, useCallback } from 'react'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { Plus, Edit2, Power, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { gridTheme } from '@/shared/grid/theme'
import { StatusBadge, type StatusBadgeColors } from '@/shared/grid/cell-renderers'
import { useColumnPersistence } from '@/shared/grid/useColumnPersistence'
import { useCarriers } from '../hooks/useCarriers'
import { useCreateCarrier, useUpdateCarrier, useDeleteCarrier } from '../hooks/useCarrierMutations'
import type { CarrierConfig, UpdateCarrierPayload } from '../types/broker'
import { CarrierForm, type CarrierFormState, EMPTY_FORM, carrierToForm, formToPayload } from '../components/CarrierForm'

const CARRIER_STATUS_COLORS: StatusBadgeColors = {
  active:   { bg: '#DCFCE7', text: '#15803D' },
  inactive: { bg: '#F3F4F6', text: '#9CA3AF' },
}

function ActionsRenderer(props: ICellRendererParams<CarrierConfig>) {
  const { openEdit, setConfirmDeactivate } = props.context as {
    openEdit: (carrier: CarrierConfig) => void
    setConfirmDeactivate: (id: string) => void
  }
  const carrier = props.data
  if (!carrier) return null

  return (
    <div className="flex items-center gap-1 h-full">
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
  )
}

const columnDefs: ColDef<CarrierConfig>[] = [
  { field: 'carrier_name', headerName: 'Name', flex: 2, minWidth: 180 },
  { field: 'carrier_type', headerName: 'Type', flex: 1, minWidth: 100 },
  { field: 'submission_method', headerName: 'Method', flex: 1, minWidth: 100 },
  {
    field: 'portal_limit',
    headerName: 'Portal Threshold',
    flex: 1,
    minWidth: 120,
    valueFormatter: (params) => params.value != null ? `$${params.value.toLocaleString()}` : '',
  },
  { field: 'email_address', headerName: 'Email', flex: 1.5, minWidth: 160 },
  {
    field: 'coverage_types',
    headerName: 'Coverage',
    flex: 1.5,
    minWidth: 140,
    valueFormatter: (params) => (params.value as string[] | null)?.join(', ') ?? '',
  },
  {
    field: 'regions',
    headerName: 'Regions',
    flex: 1,
    minWidth: 120,
    valueFormatter: (params) => (params.value as string[] | null)?.join(', ') ?? '',
  },
  {
    field: 'avg_response_days',
    headerName: 'Avg Response',
    flex: 0.8,
    minWidth: 100,
    valueFormatter: (params) => params.value != null ? `${params.value} days` : '',
  },
  {
    field: 'is_active',
    headerName: 'Status',
    flex: 0.8,
    minWidth: 100,
    cellRenderer: StatusBadge,
    cellRendererParams: { colorMap: CARRIER_STATUS_COLORS },
    valueGetter: (params) => params.data?.is_active ? 'Active' : 'Inactive',
  },
  {
    headerName: '',
    width: 90,
    pinned: 'right',
    sortable: false,
    resizable: false,
    suppressNavigable: true,
    cellRenderer: ActionsRenderer,
  },
]

export function BrokerCarriersPage() {
  const { data: carriers, isLoading } = useCarriers()
  const createMutation = useCreateCarrier()
  const updateMutation = useUpdateCarrier()
  const deleteMutation = useDeleteCarrier()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingCarrier, setEditingCarrier] = useState<CarrierConfig | null>(null)
  const [form, setForm] = useState<CarrierFormState>(EMPTY_FORM)
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(null)

  const { restoreColumnState, onColumnStateChanged, gridApiRef } =
    useColumnPersistence('broker-carriers-columns')

  const handleGridReady = useCallback(
    (e: { api: GridApi }) => {
      gridApiRef.current = e.api
      restoreColumnState(e.api)
    },
    [gridApiRef, restoreColumnState],
  )

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

  /* Loading state */
  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Carriers</h1>
        </div>
        <div className="rounded-xl border bg-white shadow-sm flex items-center justify-center" style={{ height: 300 }}>
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  /* Empty state */
  if (!carriers || carriers.length === 0) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Carriers</h1>
          <Button onClick={openCreate}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Carrier
          </Button>
        </div>
        <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          No carriers configured yet. Click Add Carrier to get started.
        </div>

        {/* Create Dialog (available in empty state) */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Carrier</DialogTitle>
            </DialogHeader>
            <CarrierForm
              form={form}
              onChange={setForm}
              onSubmit={handleSubmit}
              isSubmitting={createMutation.isPending}
              submitLabel="Add Carrier"
            />
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Carriers</h1>
        <Button onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" />
          Add Carrier
        </Button>
      </div>

      {/* Grid */}
      <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
        <div style={{ height: Math.min(carriers.length * 44 + 36, 600) }}>
          <AgGridReact<CarrierConfig>
            modules={[AllCommunityModule]}
            theme={gridTheme}
            rowData={carriers}
            columnDefs={columnDefs}
            getRowId={(params) => params.data.id}
            onGridReady={handleGridReady}
            onColumnResized={onColumnStateChanged}
            onColumnMoved={onColumnStateChanged}
            onColumnVisible={onColumnStateChanged}
            defaultColDef={{ resizable: true, sortable: true, filter: true }}
            sortingOrder={['asc', 'desc', null]}
            context={{ openEdit, setConfirmDeactivate }}
          />
        </div>
      </div>

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
