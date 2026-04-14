import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createClientContact, updateClientContact, deleteClientContact } from '../api'
import type { CreateClientContactPayload, UpdateContactPayload } from '../types/broker'

export function useCreateClientContact(clientId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateClientContactPayload) => createClientContact(clientId, payload),
    onSuccess: () => { toast.success('Contact added') },
    onError: () => { toast.error('Failed to add contact') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-client-contacts', clientId] }) },
  })
}

export function useUpdateClientContact(clientId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ contactId, payload }: { contactId: string; payload: UpdateContactPayload }) =>
      updateClientContact(clientId, contactId, payload),
    onSuccess: () => { toast.success('Contact updated') },
    onError: () => { toast.error('Failed to update contact') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-client-contacts', clientId] }) },
  })
}

export function useDeleteClientContact(clientId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (contactId: string) => deleteClientContact(clientId, contactId),
    onSuccess: () => { toast.success('Contact removed') },
    onError: () => { toast.error('Failed to remove contact') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-client-contacts', clientId] }) },
  })
}
