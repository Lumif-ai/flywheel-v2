import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createCarrier, updateCarrier, deleteCarrier } from '../api'
import type { CreateCarrierPayload, UpdateCarrierPayload } from '../types/broker'

export function useCreateCarrier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateCarrierPayload) => createCarrier(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-carriers'] })
    },
  })
}

export function useUpdateCarrier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateCarrierPayload }) =>
      updateCarrier(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-carriers'] })
    },
  })
}

export function useDeleteCarrier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteCarrier(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-carriers'] })
    },
  })
}
