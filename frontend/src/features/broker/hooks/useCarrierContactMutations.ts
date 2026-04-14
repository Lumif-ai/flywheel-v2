import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createCarrierContact, updateCarrierContact, deleteCarrierContact } from '../api'
import type { CreateCarrierContactPayload, UpdateContactPayload } from '../types/broker'

export function useCreateCarrierContact(carrierId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateCarrierContactPayload) => createCarrierContact(carrierId, payload),
    onSuccess: () => { toast.success('Contact added') },
    onError: () => { toast.error('Failed to add contact') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-carrier-contacts', carrierId] }) },
  })
}

export function useUpdateCarrierContact(carrierId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ contactId, payload }: { contactId: string; payload: UpdateContactPayload }) =>
      updateCarrierContact(carrierId, contactId, payload),
    onSuccess: () => { toast.success('Contact updated') },
    onError: () => { toast.error('Failed to update contact') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-carrier-contacts', carrierId] }) },
  })
}

export function useDeleteCarrierContact(carrierId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (contactId: string) => deleteCarrierContact(carrierId, contactId),
    onSuccess: () => { toast.success('Contact removed') },
    onError: () => { toast.error('Failed to remove contact') },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['broker-carrier-contacts', carrierId] }) },
  })
}
