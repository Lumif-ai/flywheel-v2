import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createClient, updateClient, deleteClient } from '../api'
import type { CreateClientPayload } from '../types/broker'

export function useCreateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateClientPayload) => createClient(payload),
    onSuccess: (_r, vars) => { toast.success(`Client "${vars.name}" created`) },
    onError: () => { toast.error('Failed to create client') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-clients'] }) },
  })
}

export function useUpdateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<CreateClientPayload> }) =>
      updateClient(id, payload),
    onSuccess: () => { toast.success('Client updated') },
    onError: () => { toast.error('Failed to update client') },
    onSettled: (_r, _e, vars) => {
      qc.invalidateQueries({ queryKey: ['broker-clients'] })
      qc.invalidateQueries({ queryKey: ['broker-client', vars.id] })
    },
  })
}

export function useDeleteClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteClient(id),
    onSuccess: () => { toast.success('Client deleted') },
    onError: () => { toast.error('Failed to delete client') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-clients'] }) },
  })
}
