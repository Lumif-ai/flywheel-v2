import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { AllCommunityModule } from 'ag-grid-community'
import type { ColDef, GridApi, ICellRendererParams } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { Plus, Edit2, Trash2, Loader2, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { gridTheme } from '@/shared/grid/theme'
import { DateCell } from '@/shared/grid/cell-renderers'
import { useColumnPersistence } from '@/shared/grid/useColumnPersistence'
import { useClients } from '../hooks/useClients'
import { useCreateClient, useUpdateClient, useDeleteClient } from '../hooks/useClientMutations'
import type { BrokerClient, CreateClientPayload } from '../types/broker'

function ActionsRenderer(props: ICellRendererParams<BrokerClient>) {
  const { openEdit, onDeleteRow } = props.context as {
    openEdit: (row: BrokerClient) => void
    onDeleteRow: (row: BrokerClient) => void
  }
  const row = props.data
  if (!row) return null

  return (
    <div className="flex items-center gap-1 h-full">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={(e) => { e.stopPropagation(); openEdit(row) }}
      >
        <Edit2 className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 text-red-500 hover:text-red-600"
        onClick={(e) => { e.stopPropagation(); onDeleteRow(row) }}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

const columnDefs: ColDef<BrokerClient>[] = [
  { field: 'name',       headerName: 'Name',     flex: 2, minWidth: 180 },
  { field: 'industry',   headerName: 'Industry', flex: 1, minWidth: 120 },
  { field: 'location',   headerName: 'Location', flex: 1, minWidth: 120 },
  { field: 'domain',     headerName: 'Domain',   flex: 1, minWidth: 120 },
  {
    field: 'created_at',
    headerName: 'Created',
    flex: 1,
    minWidth: 120,
    cellRenderer: DateCell,
  },
  {
    headerName: '',
    width: 90,
    pinned: 'right' as const,
    sortable: false,
    resizable: false,
    suppressNavigable: true,
    cellRenderer: ActionsRenderer,
  },
]

interface ClientFormState {
  name: string
  industry: string
  location: string
  domain: string
  notes: string
}

const EMPTY_FORM: ClientFormState = {
  name: '',
  industry: '',
  location: '',
  domain: '',
  notes: '',
}

function clientToForm(client: BrokerClient): ClientFormState {
  return {
    name:     client.name ?? '',
    industry: client.industry ?? '',
    location: client.location ?? '',
    domain:   client.domain ?? '',
    notes:    client.notes ?? '',
  }
}

export function BrokerClientsPage() {
  const navigate = useNavigate()

  /* Search with 300ms debounce */
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  const { data, isLoading } = useClients({ search: search || undefined })
  const clients = data?.items ?? []

  const createMutation = useCreateClient()
  const updateMutation = useUpdateClient()
  const deleteMutation = useDeleteClient()

  /* Dialog state */
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<BrokerClient | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [form, setForm] = useState<ClientFormState>(EMPTY_FORM)

  /* Column persistence */
  const { restoreColumnState, onColumnStateChanged, gridApiRef } =
    useColumnPersistence('broker-clients-columns')

  const handleGridReady = useCallback(
    (e: { api: GridApi }) => {
      gridApiRef.current = e.api
      restoreColumnState(e.api)
    },
    [gridApiRef, restoreColumnState],
  )

  function openCreate() {
    setForm(EMPTY_FORM)
    setCreateOpen(true)
  }

  function openEdit(row: BrokerClient) {
    setEditTarget(row)
    setForm(clientToForm(row))
    setEditOpen(true)
  }

  function onDeleteRow(row: BrokerClient) {
    if (!window.confirm(`Delete client "${row.name}"?`)) return
    deleteMutation.mutate(row.id)
  }

  function buildPayload(f: ClientFormState): CreateClientPayload {
    const p: CreateClientPayload = { name: f.name }
    if (f.industry.trim()) p.industry = f.industry.trim()
    if (f.location.trim()) p.location = f.location.trim()
    if (f.domain.trim())   p.domain   = f.domain.trim()
    if (f.notes.trim())    p.notes    = f.notes.trim()
    return p
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    createMutation.mutate(buildPayload(form), {
      onSuccess: () => setCreateOpen(false),
    })
  }

  function handleEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!editTarget) return
    updateMutation.mutate(
      { id: editTarget.id, payload: buildPayload(form) },
      { onSuccess: () => setEditOpen(false) },
    )
  }

  /* Loading state */
  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Clients</h1>
        </div>
        <div
          className="rounded-xl border bg-white shadow-sm flex items-center justify-center"
          style={{ height: 300 }}
        >
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Clients</h1>
        <Button onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" />
          Add Client
        </Button>
      </div>

      {/* Search bar */}
      <div className="relative max-w-xs">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-8"
          placeholder="Search clients…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
      </div>

      {/* Grid or empty state */}
      {clients.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          No clients yet. Click Add Client to get started.
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
          <div style={{ height: Math.min(clients.length * 44 + 36, 600) }}>
            <AgGridReact<BrokerClient>
              modules={[AllCommunityModule]}
              theme={gridTheme}
              rowData={clients}
              columnDefs={columnDefs}
              getRowId={(params) => params.data.id}
              onGridReady={handleGridReady}
              onColumnResized={onColumnStateChanged}
              onColumnMoved={onColumnStateChanged}
              onColumnVisible={onColumnStateChanged}
              defaultColDef={{ resizable: true, sortable: true, filter: true }}
              sortingOrder={['asc', 'desc', null]}
              context={{ openEdit, onDeleteRow }}
              onRowClicked={(e) => {
                if (e.data) navigate(`/broker/clients/${e.data.id}`)
              }}
            />
          </div>
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Client</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="client-name">Name *</label>
              <Input
                id="client-name"
                required
                placeholder="Acme Corp"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="client-industry">Industry</label>
              <Input
                id="client-industry"
                placeholder="e.g. Technology"
                value={form.industry}
                onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="client-location">Location</label>
              <Input
                id="client-location"
                placeholder="e.g. San Francisco, CA"
                value={form.location}
                onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="client-domain">Domain</label>
              <Input
                id="client-domain"
                placeholder="e.g. acme.com"
                value={form.domain}
                onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="client-notes">Notes</label>
              <Input
                id="client-notes"
                placeholder="Optional notes"
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Adding…' : 'Add Client'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Client</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="edit-client-name">Name *</label>
              <Input
                id="edit-client-name"
                required
                placeholder="Acme Corp"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="edit-client-industry">Industry</label>
              <Input
                id="edit-client-industry"
                placeholder="e.g. Technology"
                value={form.industry}
                onChange={(e) => setForm((f) => ({ ...f, industry: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="edit-client-location">Location</label>
              <Input
                id="edit-client-location"
                placeholder="e.g. San Francisco, CA"
                value={form.location}
                onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="edit-client-domain">Domain</label>
              <Input
                id="edit-client-domain"
                placeholder="e.g. acme.com"
                value={form.domain}
                onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="edit-client-notes">Notes</label>
              <Input
                id="edit-client-notes"
                placeholder="Optional notes"
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving…' : 'Save Changes'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
